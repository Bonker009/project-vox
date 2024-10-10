from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from langserve import add_routes
from app.api.auth import auth
from app.final_chain import chain
from app.database import engine
from app.models import otp, user
from app.core.config import settings

app = FastAPI()

user.Base.metadata.create_all(bind=engine)
otp.Base.metadata.create_all(bind=engine)

@app.get("/")
async def redirect_root_to_docs():
    return RedirectResponse("/docs")


# Edit this to add the chain you want to add
# add_routes(app, chain)

# Include the users API
app.include_router(auth.router, prefix="/api", tags=["Auth"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
