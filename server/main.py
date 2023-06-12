# This is a version of the main.py file found in ../../server/main.py that also gives ChatGPT access to the upsert endpoint
# (allowing it to save information from the chat back to the vector) database.
# Copy and paste this into the main file at ../../server/main.py if you choose to give the model access to the upsert endpoint
# and want to access the openapi.json when you run the app locally at http://0.0.0.0:8000/sub/openapi.json.
import os
from typing import Optional
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Depends, Body, UploadFile
#from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from loguru import logger

from models.api import (
    DeleteRequest,
    DeleteResponse,
    QueryRequest,
    QueryResponse,
    UpsertRequest,
    UpsertResponse,
)
from datastore.factory import get_datastore
#from services.file import get_document_from_file

from models.models import DocumentMetadata, Source

from dotenv import load_dotenv
load_dotenv()  # take environment variables from .env.

#Bearer Token Validation
"""bearer_scheme = HTTPBearer()
BEARER_TOKEN = os.environ.get("BEARER_TOKEN")
assert BEARER_TOKEN is not None


def validate_token(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    if credentials.scheme != "Bearer" or credentials.credentials != BEARER_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing token")
    return credentials
"""

app = FastAPI()
app.mount("/.well-known", StaticFiles(directory=".well-known"), name="static")

# Create a sub-application, in order to access just the upsert and query endpoints in the OpenAPI schema, found at http://0.0.0.0:8000/sub/openapi.json when the app is running locally
sub_app = FastAPI(
    title="Retrieval Plugin API",
    description="Eine retrieval API um mit Queries in natürlicher Sprache und Metdata-Filtern auf Dokumente und gespeicherte Informationen zuzugreifen",
    version="1.0.0",
    servers=[{"url": "https://your-app-url.com"}],
    #dependencies=[Depends(validate_token)],
)
app.mount("/sub", sub_app)


@app.post(
    "/upsert-file",
    response_model=UpsertResponse,
)
async def upsert_file(
    file: UploadFile = File(...),
    metadata: Optional[str] = Form(None),
):
    try:
        metadata_obj = (
            DocumentMetadata.parse_raw(metadata)
            if metadata
            else DocumentMetadata(source=Source.file)
        )
    except:
        metadata_obj = DocumentMetadata(source=Source.file)

    document = await get_document_from_file(file, metadata_obj)

    try:
        ids = await datastore.upsert([document])
        return UpsertResponse(ids=ids)
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail=f"str({e})")


@app.post(
    "/upsert",
    response_model=UpsertResponse,
)
async def upsert_main(
    request: UpsertRequest = Body(...),
    #token: HTTPAuthorizationCredentials = Depends(validate_token),
):
    try:
        ids = await datastore.upsert(request.documents)
        return UpsertResponse(ids=ids)
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail="Internal Service Error")


@sub_app.post(
    "/upsert",
    response_model=UpsertResponse,
    # NOTE: We are describing the shape of the API endpoint input due to a current limitation in parsing arrays of objects from OpenAPI schemas. This will not be necessary in the future.
    description="Speichert Chat-Informationen. Akzeptiert ein Array von Dokumenten mit Text (mögliche Fragen + Gesprächstext), Metadaten (Quelle 'chat' und Zeitstempel, keine ID, da diese generiert wird). Lass den Nutzer vor dem Speichern bestätigen und frage ggf. nach mehr Details/Kontext.",
)
async def upsert(
    request: UpsertRequest = Body(...),
    #token: HTTPAuthorizationCredentials = Depends(validate_token),
):
    try:
        ids = await datastore.upsert(request.documents)
        return UpsertResponse(ids=ids)
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail="Internal Service Error")


@app.post(
    "/query",
    response_model=QueryResponse,
)
async def query_main(
    request: QueryRequest = Body(...),
    #token: HTTPAuthorizationCredentials = Depends(validate_token),
):
    try:
        results = await datastore.query(
            request.queries,
        )
        return QueryResponse(results=results)
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail="Internal Service Error")


@sub_app.post(
    "/query",
    response_model=QueryResponse,
    # NOTE: We are describing the shape of the API endpoint input due to a current limitation in parsing arrays of objects from OpenAPI schemas. This will not be necessary in the future.
    description="Akzeptiert ein Array von search query objects, jeweils mit query und optionalem filter. Teile komplexe Fragen in Teilfragen auf. Du kannst die Ergebnisse nach Kriterien, z. B. Zeit / Quelle filtern, allerdings nicht oft. Teile die Queries auf, wenn ein ResponseTooLargeError auftritt.",
)
async def query(
    request: QueryRequest = Body(...),
    #token: HTTPAuthorizationCredentials = Depends(validate_token),
):
    try:
        results = await datastore.query(
            request.queries,
        )
        return QueryResponse(results=results)
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail="Internal Service Error")


@app.delete(
    "/delete",
    response_model=DeleteResponse,
)
async def delete(
    request: DeleteRequest = Body(...),
    #token: HTTPAuthorizationCredentials = Depends(validate_token),
):
    if not (request.ids or request.filter or request.delete_all):
        raise HTTPException(
            status_code=400,
            detail="One of ids, filter, or delete_all is required",
        )
    try:
        success = await datastore.delete(
            ids=request.ids,
            filter=request.filter,
            delete_all=request.delete_all,
        )
        return DeleteResponse(success=success)
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail="Internal Service Error")


@app.on_event("startup")
async def startup():
    global datastore
    datastore = await get_datastore()


def start():
    uvicorn.run("server.main:app", host="0.0.0.0", port=8000, reload=True)
