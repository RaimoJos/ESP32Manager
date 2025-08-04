import asyncio
import json
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import StreamingResponse
from esp32_manager.core.project_manager import ProjectManager
from esp32_manager.core.build_system import BuildManager
from esp32_manager.core.device_manager import ESP32DeviceManager

def create_app(
        project_manager: ProjectManager,
        build_manager: BuildManager,
        device_manager: ESP32DeviceManager,
) -> FastAPI:
    """Create the FastAPI application for the web interface."""
    repo_root = Path(__file__).resolve().parents[2]
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

    @app.get("/api/events")
    async def stream_events():
        """SSE endpoint that pushes the full projects and devices lists every 5 seconds."""

        async def event_generator():
            while True:
                projects = []
                for p in project_manager.list_projects():
                    status = build_manager.get_build_status(p.name)
                    last_success = status.get("last_success")
                    if last_success:
                        last_success = datetime.fromtimestamp(last_success).isoformat()
                    proj = p.to_dict()
                    proj["last_success"] = last_success
                    projects.append(proj)

                data = {
                    "projects": projects,
                    "devives": [d.to_dict() for d in device_manager.get_devices()]
                }
                yield f"data: {json.dumps(data)}\n\n"
                await asyncio.sleep(5)

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    @app.get("/api/projects")
    async def get_projects():
        """API endpoint to list projects."""
        projects = []
        for p in project_manager.list_projects():
            status = build_manager.get_build_status(p.name)
            last_success = status.get("last_success")
            if last_success:
                last_success = datetime.fromtimestamp(last_success).isoformat()
            proj = p.to_dict()
            proj["last_success"] = last_success
            projects.append(proj)
        return {"projects": projects}

    @app.post("/api/projects")
    async def create_project(request: Request):
        """Create a new project."""
        data = await request.json()
        name = data.get("name")
        description = data.get("description", "")
        template = data.get("template", "basic")
        author = data.get("author", "")
        if not name:
            raise HTTPException(status_code=400, detail="Project name is required")
        try:
            project = project_manager.create_project(
                name=name,
                description=description,
                template=template,
                author=author
            )
            return {"success": True, "project": project.to_dict()}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.delete("/api/projects/{project_name}")
    async def delete_project(project_name: str, request: Request):
        """Delete an existing project. Optional body: {'remove_file': True}."""
        try:
            data = await request.json()
        except Exception:
            data = {}
        remove_files = bool(data.get("remove_files", False))
        try:
            project_manager.delete_project(project_name, remove_files=remove_files)
            return {"success": True}
        except Exception as e:
            raise HTTPException(status_code=404, detail=str(e))

    @app.post("/api/deploy/{project_name}")
    async def deploy_project_endpoint(project_name: str, request: Request):
        """Build and deploy a project to an ESP32 device.
        JSON body must include the 'port' to use."""
        data = await request.json()
        port = data.get("port")
        if not port:
            raise HTTPException(status_code=400, detail="Device port is required")
        project = project_manager.get_project(project_name)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        # build the project
        build_result = build_manager.build_project(project)
        if not build_result.success:
            return {
                "success": False,
                "errors": build_result.errors,
                "warnings": build_result.warnings,
            }
        # deploy to the device
        transfer_result = device_manager.deploy_project(build_result.build_path, port)
        return {
            "success": transfer_result.success,
            "files_transferred": transfer_result.files_transferred,
            "bytes_transferred": transfer_result.bytes_transferred,
            "transfer_time": transfer_result.transfer_time,
            "errors": transfer_result.errors,
        }
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
            "errors": result.errors,
        }

    @app.get("/api/projects/{project_name}/info")
    async def get_project_info(project_name: str):
        """Return detailed info and stats for a project."""
        project = project_manager.get_project(project_name)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        stats = project_manager.get_project_stats(project_name)
        build_status = build_manager.get_build_status(project_name)
        last_success = build_status.get("last_success")
        if last_success:
            last_success = datetime.fromtimestamp(last_success).isoformat()
        return {
            "project": project.to_dict(),
            "stats": stats,
            "build_status": {
                "last_success": last_success,
                "last_errors": build_status.get("errors", []),
                "last_warnings": build_status.get("warnings", []),
            }
        }

    @app.get("/api/devices")
    async def get_devices():
        """API endpoint to list connected devices."""
        return {"devices": [d.to_dict() for d in device_manager.get_devices()]}
    return app