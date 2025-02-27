from fastapi import APIRouter, Depends, HTTPException
import os
from app.routes.admin import verify_api_key
import webbrowser
from fastapi import BackgroundTasks
from contextlib import asynccontextmanager
from app.services.langchain_service import LLMService

router = APIRouter(prefix="/monitoring", tags=["monitoring"])

@router.get("/workflow-graph", dependencies=[Depends(verify_api_key)])
async def get_workflow_graph():
    """Get the workflow graph visualization"""
    import tempfile
    from fastapi.responses import FileResponse
    
    # Create a temporary file for the graph
    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as temp:
        temp_path = temp.name
    
    # Get the service instance
    service = LLMService()
    
    # Generate the workflow visualization using langgraph
    try:
        # Use the newer langgraph visualization method
        img_data = service.workflow.get_graph().draw_mermaid_png()
        
        # Save the image to the temporary file
        with open(f"{temp_path}.png", "wb") as f:
            f.write(img_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate graph: {str(e)}")
    
    # Return the file
    return FileResponse(
        f"{temp_path}.png", 
        media_type="image/png",
        filename="workflow_graph.png"
    )

@router.get("/start-langgraph-studio", dependencies=[Depends(verify_api_key)])
def start_langgraph_studio(background_tasks: BackgroundTasks):
    """Start LangGraph Studio in the background"""
    
    def run_langgraph_studio():
        import subprocess
        import os
        
        try:
            # Get the current working directory
            cwd = os.getcwd()
            print(f"Starting LangGraph Studio from {cwd}")
            
            # Start LangGraph Studio
            process = subprocess.Popen(
                ["poetry", "run", "langgraph-studio"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=cwd
            )
            
            # Return the process output
            stdout, stderr = process.communicate()
            if stderr:
                print(f"Error starting LangGraph Studio: {stderr}")
            
        except Exception as e:
            print(f"Failed to start LangGraph Studio: {e}")
    
    # Run in background
    background_tasks.add_task(run_langgraph_studio)
    
    return {"message": "Starting LangGraph Studio. Please open the desktop app."}

@asynccontextmanager
async def lifespan(app):
    # Startup code
    if os.getenv("AUTO_START_LANGGRAPH", "true").lower() == "true":
        import threading
        import time
        
        def delayed_start():
            time.sleep(2)
            # Start LangGraph Studio
            import subprocess
            print("🚀 Starting LangGraph Studio...")
            subprocess.Popen(
                ["poetry", "run", "langgraph-studio"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        
        threading.Thread(target=delayed_start).start()
    
    yield
    
    # Shutdown code (if any) 