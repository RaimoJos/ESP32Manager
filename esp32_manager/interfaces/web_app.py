from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from esp32_manager.core.project_manager import ProjectManager
from esp32_manager.core.build_system import BuildManager
from esp32_manager.core.device_manager import ESP32DeviceManager

def create_app(
        project_manager: ProjectManager,
        build_manager: BuildManager,
        device_manager: ESP32DeviceManager,
) -> FastAPI:
    """Create the FastAPI application for the web interface."""
    repo_root = Path(__file__).resolve().parent[2]
    static_dir = repo_root / "web_interface" / "static"
    templates_dir = repo_root / "web_interface" / "templates"

    app = FastAPI(title="ESP32 Manager Web")

    # Static files and templates
    app.mount("/static", StaticFiles(directory=str(static_dir)),
              name="static")
    templates = Jinja2Templates(directory=str(templates_dir))

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        """Render dashboard page."""
        projects = [p.to_dict() for p in project_manager.list_projects()]
        devices = [d.to_dict() for d in device_manager.get_devices()]
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "projects": projects,
                "devices": devices,
            }
        )

    @app.get("/api/projects")
    async def get_projects():
        """API endpoint to list projects."""
        return {"projects": [p.to_dict() for p in project_manager.list_projects()]}

    @app.post("/api/build/{project_name}")
    async def build_project(project_name: str):
        """Start a build for the given project."""
        project = project_manager.get_project(project_name)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        result = build_manager.build_project(project)
        return {
            "success": result.success,
            "files_processed": result.files_processed,
            "total_size": result.total_size,
            "build_time": result.build_time,
            "warnings": result.errors,
        }

    @app.get("/api/devices")
    async def get_devices():
        """API endpoint to list connected devices."""
        return {"devices": [d.to_dict() for d in device_manager.get_devices()]}
    return app