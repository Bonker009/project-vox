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


groq_api_key = config("GROQ_API_KEY")
client = Groq(api_key=groq_api_key)
# db = SQLDatabase.from_uri(config("POSTGRES_URL"))
db = SQLDatabase.from_uri("postgresql://postgres:1234@localhost:5432/event_management_db")
print(db.dialect)
print(db.get_usable_table_names())

llm = ChatGroq(
    model="llama-3.1-70b-versatile",
    temperature=0,
    max_tokens=None,
    max_retries=10,
    timeout=None,
)

chain = create_sql_query_chain(llm, db)


def run_read_only_query(query):
    # (Fore.CYAN, query.strip())

    if "Sorry" in query.strip():
        # (Fore.RED, query)
        return query
    execution_options = {"isolation_level": "READ ONLY"}
    try:
        result = db.run(command=query, execution_options=execution_options)

        print(Fore.GREEN, result)
        return result
    except Exception as e:
        return f"An error occurred: {e}"


def get_schema(_):
    return db.get_table_info()


def validate_sql(query):
    match = re.search(r"```(?:sql)?\s*(.*?)\s*```", query, re.DOTALL)
    if match:
        query = match.group(1).strip()
    print(Fore.RED, "This is the SQL query: ", query, Fore.RESET)
    if not query:
        raise ValueError("Generated SQL query is empty or invalid.")
    if not query.upper().startswith("SELECT"):
        return "Sorry, data modification (e.g., INSERT, UPDATE, DELETE) or structural changes (e.g., CREATE, DROP, ALTER) are not allowed in read-only mode."

    # Use LLM to further analyze the prompt via a prompt template
    prompt = sensitive_info_prompt_template.format(question=query)
    human_message = HumanMessage(content=prompt)
    response = llm.invoke([human_message])

    # Check the LLM's response and decide if the query should be refined
    if "safe to proceed" in response.content.lower():
        # ("LLM confirmed the query is safe to proceed.")
        return query
    else:
        # (f"LLM response: {response.content}")
        return """You have asked for information that is restricted or sensitive, such as passwords or other confidential data. For security and privacy reasons, this type of information cannot be provided.
                Please note that attempting to access sensitive or restricted data goes against our policies. If you have any other questions or need further assistance, feel free to ask!"""


# PromptTemplate for warning about sensitive information or modification requests
sensitive_info_prompt_template = PromptTemplate.from_template(
    """
  You are an AI assistant responsible for analyzing SQL queries and ensuring that sensitive information is not exposed.

The user has asked the following query: "{question}"

Please follow these instructions when processing the query:

1. **Check for Sensitive Information**: If the query involves any of the following sensitive fields, remove them from the results:
   - Passwords
   - OTP codes
   - Social Security numbers (SSN)
   - Driver's license numbers
   - Passport numbers
   - Credit card numbers
   - Debit card numbers
   - Bank account numbers

2. **Handling Sensitive Fields**:
    - **If the query only requests sensitive fields**, such as 'SELECT password FROM users', return a warning message saying:
      - "Sensitive information like passwords, credit card numbers, or Social Security numbers cannot be retrieved for security reasons. Please refine your query to request non-sensitive data."

    - **If the query includes both sensitive and non-sensitive fields**, return only the non-sensitive fields.
      - Example: If the query is 'SELECT name, email, password FROM users', respond with 'name' and 'email', but exclude 'password'.

    - Always ensure that sensitive fields are filtered out and provide the user with a safe response.

3. **Safe Response**:
    - **If no sensitive fields are found**, return the data normally and include a message like:
      - "Safe to proceed. No sensitive data detected in the query."

    - **If sensitive fields are found and removed**, return the modified result and say:
      - "Safe to proceed. The sensitive fields have been excluded, and the remaining data is: [list of non-sensitive columns]."

The SQL query you need to process is: "{question}"
    """
)


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


visualization_detection_prompt_template = PromptTemplate.from_template(
    """
    You are an AI assistant responsible for determining whether the user is asking for any form of data visualization.
    Data visualizations refer to visual representations of data such as charts, graphs, plots, or similar formats.

    Visualizations may include specific types such as:
    - Bar chart
    - Line graph
    - Pie chart
    - Scatter plot
    - Histogram
    - Heatmap
    - Or any other visual representation of data

    Additionally, if the user simply requests a "visualization" or "visualizations"  without specifying the type (e.g., "Show me a visualization of members"),
    you should still respond with 'yes', as the user is clearly asking for some form of data visualization.

    If the user's input indicates they are asking for a data visualization of any kind, respond with 'yes'.
    If the user's input does not indicate a request for a data visualization, respond with 'no'.

    Be concise and respond with only 'yes' or 'no'.

    User input: "{input}"
    Visualization requested: """
)


def check_for_visualization_request(llm, user_input):
    # ("Please respond with")
    """Use the LLM to check if the user's input is asking for a chart or visualization."""

    prompt = visualization_detection_prompt_template.format(input=user_input)

    human_message = HumanMessage(content=prompt)
    response = llm.invoke([human_message])
    # (Fore.CYAN, response.content, Fore.RESET)
    is_visualization_requested = response.content.strip().lower()
    return is_visualization_requested == "no"


def clean_code(response_content):

    lines = response_content.splitlines()

    cleaned_code_lines = []

    code_like_pattern = re.compile(
        r"^[\s]*(import|from|def|class|if|else|for|while|try|except|return|with|plt\.|pd\.)|^[\s]*#"
    )

    for line in lines:

        if code_like_pattern.match(line) or line.strip().startswith(
            ("", "    ", "plt", "os", "uuid")
        ):
            cleaned_code_lines.append(line)

    cleaned_code = "\n".join(cleaned_code_lines)
    return cleaned_code


def ask_llm_to_generate_code(
    llm, sql_query, result, chart_type="bar", library="matplotlib"
):
    # (Fore.LIGHTYELLOW_EX, result, Fore.RESET)

    if not result or len(result) == 0:
        raise ValueError(
            "SQL query result is empty. Visualization cannot be generated."
        )

    prompt = f"""
You are an AI assistant that generates appropriate Python code to visualize data.

Based on the SQL query, its result, and the desired chart type, generate Python code that visualizes the data. The chart types and their use cases are:

- Bar Graph: Compare categorical data or show changes over time with discrete categories.
- Horizontal Bar Graph: Compare small categories or when there is a large disparity between values.
- Scatter Plot: Identify relationships between two numerical variables or plot distributions.
- Pie Chart: Show proportions or percentages within a whole.
- Line Graph: Show trends and distributions over time (both axes must be continuous).

The SQL query result is provided below as a list of dictionaries:
{result}

Please follow these additional instructions:
- Only generate the required Python code.
- Do not include any markdown formatting, including backticks or triple backticks.
- Use pandas to create a DataFrame from the result.
- Retrieve the column names or table names directly from the database for the x-axis and y-axis labels.
- Do not use `plt.show()` to display the chart. Instead, save the chart as an image file using `plt.savefig()`.
- Use the first column from the query result for the x-axis label and the second column for the y-axis label.
- Generate a {chart_type} using the {library} library.
- Import matplotlib and use a non-interactive backend:
    matplotlib.use('Agg')

- Show gridlines on the canvas.

The generated code should:
- Create a directory named 'visualization' if it doesn't exist.
- Save the chart to the 'visualization' directory with a unique filename (use the `uuid` module to generate a unique identifier with type of chart and current date).
- Do not include any explanatory text or markdown formatting, only return Python code.
"""

    human_message = HumanMessage(content=prompt)
    response = llm.invoke([human_message])
    # ("hello my dear : " + Fore.RED, response.content, Fore.RESET)

    cleaned_code = (
        clean_code(response.content) if "clean_code" in globals() else response.content
    )

    print("Generated Python code:\n", cleaned_code, "\nEnd")

    return cleaned_code


def execute_generated_code(generated_code, output_folder="images"):
    # (Fore.RED, generated_code)

    try:
        if not isinstance(generated_code, str):
            return "Error: The generated code is not a string."
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
            # (f"Folder '{output_folder}' created successfully.")
        unique_id = uuid.uuid4()
        current_date = datetime.now().strftime("%Y%m%d")
        file_name = f"plot_{current_date}_{unique_id}.png"
        output_path = os.path.join(output_folder, file_name)
        exec(generated_code, globals())
        return f"Plot saved successfully at {output_path}", file_name

    except Exception as e:
        return f"An error occurred while executing the generated code: {e}", None


def handle_user_query(llm, user_query):

    if check_for_visualization_request(llm, user_query):
        # (Fore.LIGHTYELLOW_EX, "Hello World", Fore.RESET)
        sql_result = run_read_only_query(validate_sql(user_query))
        # (Fore.CYAN, sql_result)
        generated_code = ask_llm_to_generate_code(llm, user_query, sql_result)
        # (Fore.BLUE, generated_code, Fore)
        plot_path = execute_generated_code(generated_code)
        # ("Hello magic")
        # (Fore.GREEN, plot_path)

        return f"Visualization has been generated and saved at {plot_path}."
    else:
        return run_read_only_query(validate_sql(user_query))


def get_history(x):
    history = memory.load_memory_variables(x)["history"]
    print(history)
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

template = """
Based on the table schema below, question, SQL query, and SQL response, write a natural language response:
{schema}

Question: {question}
SQL Query: {query}
SQL Response: {response}

Your response must be accurate and based strictly on the SQL result provided. Ensure the following:
- Reflect the exact numbers or data from the SQL response.
- Avoid assumptions or generalizations not directly supported by the SQL result.
- If the SQL response contains numerical data (e.g., a count), your natural language response must include the correct number based on the SQL result.
- Verify that the SQL result has been processed correctly before generating the final natural language response.
- Be concise and ensure no extra information is added beyond what is requested.

For example, if the SQL response shows a count of customers, your natural language response should exactly match the count in the SQL result (e.g., "There are 5 customers in the database" for an SQL result of [(5,)]).
"""

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
Based on the table schema below, question, SQL query, and SQL response, write a natural language response:
{schema}

Question: {question}
SQL Query: {query}
SQL Response: {response}

Your response must accurately reflect the SQL result. For example, if the SQL response shows a count of customers, your natural language response must reflect the correct number based on the SQL result.
Please do not assume or guess, the response should be purely based on the SQL result.
"""

response_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "Given the input question and SQL response, convert it to a natural language answer. No pre-amble."),
        ("human", response_template)
    ]
)

chain = (
    RunnablePassthrough.assign(query=sql_response_memory).with_types(input_type=InputType)
    | RunnablePassthrough.assign(
        schema=get_schema,
        response=lambda x: (
            print(f"Result from handle_user_query: {handle_user_query(llm, x['query'])}")
            or handle_user_query(llm, x["query"]) 
        )
    )
    | (
        lambda x: (
            "Please return only : Sorry, data modification (e.g., INSERT, UPDATE, DELETE) or structural changes (e.g., CREATE, DROP, ALTER) are not allowed in read-only mode."
            if "Sorry" in x["response"]
            else response_prompt
        )
    )
    | llm
)