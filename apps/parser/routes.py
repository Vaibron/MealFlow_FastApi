from fastapi import APIRouter

router = APIRouter(prefix="/parser", tags=["parser"])

@router.get("/placeholder")
async def parser_placeholder():
    return {"message": "Parser app is not implemented yet"}