from fastapi import FastAPI, HTTPException, Query
from elasticsearch import Elasticsearch
from pydantic import BaseModel
import os
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

# Elasticsearch configuration
ES_HOST = os.getenv('ELASTICSEARCH_HOST', 'localhost')
ES_PORT = int(os.getenv('ELASTICSEARCH_PORT', 9200))

# Elasticsearch client
es = Elasticsearch(hosts=[{'host': ES_HOST, 'port': ES_PORT, 'scheme': 'http'}])

# Index names as defined in your main.py
DOC_INDICES = {
    'critics': 'telegram_critics',
    'critiques': 'telegram_critiques',
    'game': 'game_registrants'
}

# TV programs
TV_PROGRAMS = ['Love Island', 'Turkish News', 'Cooking Show', 'Sports Highlights']

# Initialize FastAPI
app = FastAPI(
    title="TV Channel Bot API",
    description="API for accessing critics and critiques data",
    version="1.0.0",
)

class Critic(BaseModel):
    user_id: int
    first_name: str
    last_name: str
    phone: str
    timestamp: datetime

class Critique(BaseModel):
    user_id: int
    program: str
    received_id: str
    file_path: str
    timestamp: datetime
    content_type: str
    text_content: Optional[str] = None
    voice_duration: Optional[int] = None

class GameRegistrant(BaseModel):
    user_id: int
    player_name: str
    registration_date: datetime

class SearchResult(BaseModel):
    index: str
    id: str
    source: Dict[str, Any]

@app.get("/indices", summary="List available indices")
async def get_indices():
    """Return all available indices"""
    return {"indices": list(DOC_INDICES.values())}

@app.get("/critics", response_model=List[Critic], summary="List all critics")
async def list_critics(size: int = Query(1000, description="Maximum records to return")):
    """List all registered critics"""
    return list_docs('critics', size)

@app.get("/critiques", response_model=List[Critique], summary="List all critiques")
async def list_critiques(size: int = Query(1000, description="Maximum records to return")):
    """List all submitted critiques"""
    return list_docs('critiques', size)

@app.get("/game-registrants", response_model=List[GameRegistrant], summary="List all game registrants")
async def list_game_registrants(size: int = Query(1000, description="Maximum records to return")):
    """List all game registrants"""
    return list_docs('game', size)

@app.get("/critiques/by-program/{program}", response_model=List[Critique], summary="List critiques by program")
async def critiques_by_program(
    program: str,
    size: int = Query(100, description="Maximum results to return")
):
    """List critiques for a specific TV program"""
    if program not in TV_PROGRAMS:
        raise HTTPException(status_code=400, detail="Invalid program name")
    
    try:
        query = {
            "query": {
                "term": {
                    "program.keyword": program
                }
            }
        }
        result = es.search(index=DOC_INDICES['critiques'], body=query, size=size)
        return [hit['_source'] for hit in result['hits']['hits']]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.get("/critiques/by-user/{user_id}", response_model=List[Critique], summary="List critiques by user")
async def critiques_by_user(
    user_id: int,
    size: int = Query(100, description="Maximum results to return")
):
    """List critiques submitted by a specific user"""
    try:
        query = {
            "query": {
                "term": {
                    "user_id": user_id
                }
            }
        }
        result = es.search(index=DOC_INDICES['critiques'], body=query, size=size)
        return [hit['_source'] for hit in result['hits']['hits']]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.get("/search", response_model=List[SearchResult], summary="Search across all indices")
async def full_text_search(
    query: str = Query(..., description="Search query string"),
    size: int = Query(100, description="Maximum results to return")
):
    """Search across all indices using full-text search"""
    try:
        # Create multi-match query across all fields
        search_query = {
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["*"],
                    "fuzziness": "AUTO"
                }
            }
        }
        
        # Execute search across all indices
        result = es.search(index=",".join(DOC_INDICES.values()), body=search_query, size=size)
        
        # Format results
        results = []
        for hit in result['hits']['hits']:
            results.append(SearchResult(
                index=hit['_index'],
                id=hit['_id'],
                source=hit['_source']
            ))
            
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

def list_docs(index_key: str, size: int) -> List[Dict]:
    """List documents from a specific index"""
    try:
        result = es.search(
            index=DOC_INDICES[index_key],
            body={"query": {"match_all": {}}},
            size=size
        )
        return [hit['_source'] for hit in result['hits']['hits']]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving records: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)