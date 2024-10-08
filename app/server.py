from typing import List, Tuple
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from groq import Groq
from langchain_groq import ChatGroq
from langserve import CustomUserType, add_routes
from pydantic import Field
from app.final_chain import chain
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from decouple import config
from langchain_core.runnables import (
    RunnableLambda,
    RunnablePassthrough,
    RunnableParallel,
)

app = FastAPI()

groq_api_key = config("GROQ_API_KEY")
client = Groq(api_key=groq_api_key)
llm = ChatGroq(model="llama3-8b-8192")

app.mount("/uploads", StaticFiles(directory="visualization"), name="uploads")


@app.get("/")
async def redirect_root_to_docs():
    return RedirectResponse("/docs")


class ChatHistory(CustomUserType):
    chat_history: List[Tuple[str, str]] = Field(
        ...,
        examples=[[("human input", "ai response")]],
        extra={"widget": {"type": "chat", "input": "question", "output": "answer"}},
    )
    question: str


def _format_to_messages(input: ChatHistory) -> List[BaseMessage]:
    """Format the input to a list of messages."""
    history = input.chat_history
    user_input = input.question

    messages = []

    for human, ai in history:
        messages.append(HumanMessage(content=human))
        messages.append(AIMessage(content=ai))
    messages.append(HumanMessage(content=user_input))
    return messages


chat_model = RunnableParallel({"answer": (RunnableLambda(_format_to_messages) | llm)})
add_routes(
    app,
    chat_model.with_types(input_type=ChatHistory),
    config_keys=["configurable"],
    path="/chat1",
)
# Edit this to add the chain you want to add
add_routes(
    app,
    chain,
    config_keys=["configurable"],
    path="/chat",
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
