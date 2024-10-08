from datetime import datetime
import re
import uuid
from langchain.memory import ConversationBufferMemory
from langchain_groq.chat_models import ChatGroq
from langchain_community.utilities import SQLDatabase
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from decouple import config
from langchain.chains.sql_database.query import create_sql_query_chain
from groq import Groq
from langchain_core.messages import HumanMessage
import os
import matplotlib.pyplot as plt
from colorama import Fore
from langchain_core.prompts import PromptTemplate
from langchain.chains import create_sql_query_chain

groq_api_key = config("GROQ_API_KEY")
os.environ["GROQ_API_KEY"] = groq_api_key

client = Groq(api_key=groq_api_key)

db = SQLDatabase.from_uri(config("POSTGRES_URL"))
print(db.dialect)
print(db.get_usable_table_names())

llm = ChatGroq(
    model="llama3-groq-70b-8192-tool-use-preview",
    temperature=0.7,
    max_tokens=None,
    timeout=None,
    max_retries=10
)

create_sql_chain = create_sql_query_chain(llm, db)


def run_read_only_query(query):

    if "Sorry" in query:
        return query

    execution_options = {"isolation_level": "READ ONLY"}
    try:

        result = db.run(command=query, execution_options=execution_options)
        print(Fore.GREEN,"This is Result : " , result,Fore.RESET)
        return result
    except Exception as e:
        return f"An error occurred: {e}"


def get_schema(_):
    return db.get_table_info()

 
def validate_sql(query):
    print("This is the SQL query: ", query)
    
    # Check if the query is empty
    if not query.strip():
        raise ValueError("Generated SQL query is empty or invalid.")
    
# Regular expression to match the SQL query
    sql_query = re.search(r'SELECT.*?;', query, re.DOTALL)
    print(sql_query)
    if sql_query:
        # Clean and return the SELECT query
        cleaned_query = sql_query.group(0)

        print("This is the valid SQL query:", cleaned_query)
        return cleaned_query
    else:
        # Return a message if the query contains non-SELECT commands
        return "Sorry, data modification (e.g., INSERT, UPDATE, DELETE) or structural changes (e.g., CREATE, DROP, ALTER) are not allowed in read-only mode."

template = """Based on the table schema below, write a SQL query that would answer the user's question:
{schema}

Question: {question}
SQL Query:"""
prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "Given an input question, convert it to a SQL query. No pre-amble."),
        MessagesPlaceholder(variable_name="history"),
        ("human", template),
    ]
)

visualization_detection_prompt_template = """
Is the following user query asking for a visualization (like a chart, plot, or graph)? 
Please respond with 'Yes' or 'No'.

User Query: {question}
"""

visualization_detection_prompt_template = PromptTemplate.from_template(
    """
    Given the following user input, determine if the user is asking for a data visualization (such as a chart, graph, or plot).
    Please respond with either 'yes' if visualization is requested, or 'no' if no visualization is requested.

    User input: "{input}"
    Visualization requested: """
)


def check_for_visualization_request(llm, user_input):
    """Use the LLM to check if the user's input is asking for a chart or visualization."""

    prompt = visualization_detection_prompt_template.format(input=user_input)

    human_message = HumanMessage(content=prompt)
    response = llm.invoke([human_message])

    is_visualization_requested = response.content.strip().lower()
    return is_visualization_requested == "yes"


def clean_code(response_content):
    # Split the response content by lines
    lines = response_content.splitlines()

    # Initialize a flag to identify code block and a list to store cleaned code lines
    in_code_block = False
    cleaned_code_lines = []

    for line in lines:
        # Detect the start and end of the code block
        if line.strip().startswith("```"):
            in_code_block = not in_code_block  # Toggle the flag
        elif in_code_block:
            cleaned_code_lines.append(line)

    # Join the cleaned lines to form the final cleaned code
    cleaned_code = "\n".join(cleaned_code_lines)
    return cleaned_code


def ask_llm_to_generate_code(
    llm, sql_query, result, chart_type="bar chart", library="matplotlib"
):
    # Create the prompt
    prompt = f"""
    The SQL query result is provided below as a list of dictionaries where each dictionary represents a row:
    {result}

    Based on this data, please generate Python code using {library} to create a {chart_type}.
    Ensure that the SQL query result is used to create the DataFrame or data structure for the chart.
    The axes should be appropriately labeled based on the available data and all necessary imports should be included.

    Additionally, after generating the chart, save the figure to a directory named 'visualization'.
    If this directory does not exist, please create it before saving the chart.
    Use the uuid module to generate a unique file name, combining the chart type and a unique identifier.
    """

    human_message = HumanMessage(content=prompt)
    response = llm.invoke([human_message])
    cleaned_code = clean_code(response.content)

    print("Cleaned Python code:\n", cleaned_code, "\nEnd")
    return cleaned_code


def execute_generated_code(generated_code, output_folder="images"):
    print(Fore.RED, generated_code)

    try:
        if not isinstance(generated_code, str):
            return "Error: The generated code is not a string."
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
            print(f"Folder '{output_folder}' created successfully.")
        unique_id = uuid.uuid4()
        current_date = datetime.now().strftime("%Y%m%d")
        file_name = f"plot_{current_date}_{unique_id}.png"
        output_path = os.path.join(output_folder, file_name)
        exec(generated_code, globals())
        plt.savefig(output_path)
        plt.close()
        return f"Plot saved successfully at {output_path}", file_name

    except Exception as e:
        return f"An error occurred while executing the generated code: {e}", None


def handle_user_query(llm, user_query):

    if check_for_visualization_request(llm, user_query):

        sql_result = run_read_only_query(validate_sql(user_query))
        print("SQL Result:", sql_result)
        generated_code = ask_llm_to_generate_code(llm, user_query, sql_result)
        print(Fore.BLUE, generated_code, Fore)
        plot_path = execute_generated_code(generated_code)
        print(Fore.GREEN, plot_path)

        return f"Visualization has been generated and saved at {plot_path}."
    else:
        print()
        return run_read_only_query(validate_sql(user_query))


def get_history(x):
    history = memory.load_memory_variables(x)["history"]

    if isinstance(history, str):
        return [HumanMessage(content=history)]
    return history


memory = ConversationBufferMemory()

sql_chain = (
    RunnablePassthrough.assign(
        schema=get_schema,
        history=RunnableLambda(get_history),
    )
    | prompt
    | llm.bind(stop=["\nSQLResult:"])
    | StrOutputParser()
)


def save(input_output):
    output = {"output": input_output.pop("output")}
    memory.save_context(input_output, output)
    return output["output"]


sql_response_memory = RunnablePassthrough.assign(output=sql_chain) | save

template = """Based on the table schema below, question, sql query, and sql response, write a natural language response:
{schema}

Question: {question}
SQL Query: {query}
SQL Response: {response}"""
prompt_response = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Given an input question and SQL response, convert it to a natural "
            "language answer. No pre-amble.",
        ),
        ("human", template),
    ]
)


class InputType(BaseModel):
    question: str


response_template = """
on the table schema below, question, sql query, and sql response, write a natural language response:
{schema}

Question: {question}
SQL Response: {response}"""

response_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are the expert of giving answers following user question.
            Here is the context the table schema below, question, sql query, and sql response, write a human language response:
                {schema}

                Question: {question}
                SQL Response: {response}
            """
        ),
        # ("human", response_template),
    ]
)

chain = (
    RunnablePassthrough.assign(query=sql_response_memory).with_types(
        input_type=InputType
    )
    | RunnablePassthrough.assign(
        schema=get_schema,
        response=lambda x: handle_user_query(llm, x["query"]),
    )
    | response_prompt
    | llm
)
