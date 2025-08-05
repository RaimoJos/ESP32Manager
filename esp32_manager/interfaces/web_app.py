import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from esp32_manager.core.project_manager import ProjectManager
from esp32_manager.core.build_system import BuildManager
from esp32_manager.core.device_manager import ESP32DeviceManager

# Data models for better type safety
class ProjectCreateRequest(BaseModel):
    name: str
    description: str = ""
    template: str = "basic"
    author: str = ""

class DeployRequest(BaseModel):
    port: str

class FileContent(BaseModel):
    content: str

class ProjectConfig(BaseModel):
    build_settings: Dict = {}
    deployment_settings: Dict = {}
    dependencies: List[str] = []

class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""
    def __init__(self):
        self.active_connections: List[WebSocket] = []

        self.build_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, connection_type: str = "general", project_name: str = None):
        await websocket.accept()
        if connection_type == "build" and project_name:
            self.build_connections.setdefault(project_name, []).append(websocket)
        else:
            self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket, connection_type: str = "general", project_name: str = None):
        if connection_type == "build" and project_name:
            # remove socket if present
            conns = self.build_connections.get(project_name, [])
            if websocket in conns:
                conns.remove(websocket)
            else:
                if websocket in self.active_connections:
                    self.active_connections.remove(websocket)

    async def broadcast_build_progress(self, message: dict, project_name: str):
        if project_name in self.build_connections:
            for connection in self.build_connections[project_name]:
                try:
                    await connection.send_text(json.dumps(message))
                except:
                    self.build_connections[project_name].remove(connection)


def create_app(
        project_manager: ProjectManager,
        build_manager: BuildManager,
        device_manager: ESP32DeviceManager,
) -> FastAPI:
    """Create the enhanced FastAPI application."""
    repo_root = Path(__file__).resolve().parents[2]
    static_dir = repo_root / "web_interface" / "static"
    templates_dir = repo_root / "web_interface" / "templates"

    app = FastAPI(title="ESP32 Manager Web", version="2.0.0")

    device_manager.start_scanning(interval=2.0)
    manager = ConnectionManager()

    # Static files and templates
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    templates = Jinja2Templates(directory=str(templates_dir))

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        """Render dashboard page."""
        projects = []
        for p in project_manager.list_projects():
            status = build_manager.get_build_status(p.name)
            last_success = status.get("last_success")
            if last_success:
                last_success = datetime.fromtimestamp(last_success).isoformat()
            proj = p.to_dict()
            proj["last_success"] = last_success
            projects.append(proj)

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
        """SSE endpoint with corrected typo."""
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
                    "devices": [d.to_dict() for d in device_manager.get_devices()]  # FIXED: typo
                }
                yield f"data: {json.dumps(data)}\n\n"
                await asyncio.sleep(5)

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    @app.get("/ws/logs/{port}")
    async def websocket_logs(websocket: WebSocket, port: str):
        """Websocket endpoint to stream serial logs for the given device port."""
        await websocket.accept()
        # Queue to hand off lines from SerialMonitor callback to WebSocket loop
        queue: "asyncio.Queue[str]" = asyncio.Queue()

        # Define callback to push lines into asyncio queue
        def on_line(line: str):
            # schedule queue.put in the event loop
            asyncio.create_task(queue.put(line))

        # Start monitoring; will call on_line() for each new serial line
        if not device_manager.start_monitor(port, callback=on_line):
            await websocket.close(code=1000)
            return

        try:
            # Continuously send lines as they arrive
            while True:
                line = await queue.get()
                await websocket.send_text(line)
        except WebSocketDisconnect:
            # Client disconnected, stop monitoring
            pass
        finally:
            device_manager.stop_monitor(port)

    @app.get("/api/projects")
    async def get_projects():
        """API endpoint to list projects."""
        projects = []
        for p in project_manager.list_projects():
            status = build_manager.get_build_status(p.name)
            stats = project_manager.get_project_stats(p.name)
            last_success = status.get("last_success")
            if last_success:
                last_success = datetime.fromtimestamp(last_success).isoformat()

            proj = p.to_dict()
            proj.update({
                "last_success": last_success,
                "file_count": stats.get("file_count", 0),
                "total_size": stats.get("total_size", 0),
                "python_files": stats.get("python_files", []),
                "build_errors": status.get("errors", []),
                "build_warnings": status.get("warnings", []),
            })
            projects.append(proj)
        return {"projects": projects}

    @app.post("/api/projects")
    async def create_project(request: ProjectCreateRequest):
        """Create a new project with proper validation."""
        try:
            project = project_manager.create_project(
                name=request.name,
                description=request.description,
                template=request.template,
                author=request.author,
            )
            return {"success": True, "project": project.to_dict()}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.delete("/api/projects/{project_name}")
    async def delete_project(project_name: str, request: Request):
        """Delete an existing project."""
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

    @app.get("/api/projects/{project_name}/files")
    async def list_project_files(project_name: str):
        """List all files in a project with metadata."""
        project = project_manager.get_project(project_name)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        def get_file_tree(path: Path, relative_to: Path) -> List[Dict]:
            """Recursively build file tree."""
            items = []
            if path.is_dir():
                for item in sorted(path.iterdir()):
                    if item.name.startswith('.'):
                        continue

                    rel_path = item.relative_to(relative_to)
                    if item.is_dir():
                        items.append({
                            "name": item.name,
                            "path": str(rel_path),
                            "type": "file",
                            "size": item.stat().st_size,
                            "modified": datetime.fromtimestamp(item.stat().st_mtime).isoformat()
                        })
            return items
        project_path = Path(project.path)
        files = get_file_tree(project_path, project_path)
        return {"files": files}

    @app.get("/api/projects/{project_name}/files/{file_path:path}")
    async def get_file_content(project_name: str, file_path: str):
        """Get file content for editing."""
        project = project_manager.get_project(project_name)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        full_path = Path(project.path) / file_path
        if not full_path.exists() or not full_path.is_file():
            raise HTTPException(status_code=404, detail="File not found")

        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return {
                "content": content,
                "path": file_path,
                "size": full_path.stat().st_size,
                "modified:": datetime.fromtimestamp(full_path.stat().st_mtime)
            }
        except UnicodeDecodeError:
            raise HTTPException(status_code=404, detail="File ia not text-readable")

    @app.put("/api/projects/{project_name}/files/{file_path:path}")
    async def save_file_content(project_name: str, file_path: str, request: FileContent):
        """Save edited file content."""
        project = project_manager.get_project(project_name)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        full_path = Path(project.path) / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(request.content)
            return {
                "success": True,
                "size": full_path.stat().st_size,
                " modified": datetime.fromtimestamp(full_path.stat().st_mtime).isoformat()
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

    @app.post("/api/projects/{project_name}/files/{file_path:path}")
    async def create_file(project_name: str, file_path: str, request: FileContent):
        """Create a new file."""
        project = project_manager.get_project(project_name)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        full_path = Path(project.path) / file_path
        if full_path.exists():
            raise HTTPException(status_code=409, detail="File already exists")

        full_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(request.content)
            return {"success": True, "path": file_path}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to create file: {str(e)}")

    @app.delete("/api/projects/{project_name}/files/{file_path:path}")
    async def delete_file(project_name: str, file_path: str):
        """Delete a file."""
        project = project_manager.get_project(project_name)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        full_path = Path(project.path) / file_path
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="File not found")

        try:
            if full_path.is_file():
                full_path.unlink()
            elif full_path.is_dir():
                import shutil
                shutil.rmtree(full_path)
            return {"success": True}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")

    @app.websocket("/ws/build/{project_name}")
    async def websocket_build_progress(websocket: WebSocket, project_name: str):
        await manager.connect(websocket, "build", project_name)
        try:
            while True:
                # Keep connection alive
                await asyncio.sleep(1)
        except WebSocketDisconnect:
            manager.disconnect(websocket, "build", project_name)

    @app.post("/api/deploy/{project_name}")
    async def deploy_project_endpoint(project_name: str, request: DeployRequest):
        """Build and deploy a project to an ESP32 device with progress tracking."""
        project = project_manager.get_project(project_name)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Send deploy start notification
        await manager.broadcast_build_progress({
            "type": "deploy_start",
            "project": project_name,
            "port": request.port,
            "timestamp": datetime.now().isoformat()
        }, project_name)

        try:
            # Build the project first
            build_result = build_manager.build_project(project)
            if not build_result.success:
                return {
                    "success": False,
                    "stage": "build",
                    "errors": build_result.errors,
                    "warnings": build_result.warnings,
                }

            # Deploy to the device
            transfer_result = device_manager.deploy_project(build_result.build_path, request.port)

            # Send deploy completion notification
            await manager.broadcast_build_progress({
                "type": "deploy_complete",
                "project": project_name,
                "success": transfer_result.success,
                "timestamp": datetime.now().isoformat()
            }, project_name)

            return {
                "success": transfer_result.success,
                "stage": "deploy",
                "files_transferred": transfer_result.files_transferred,
                "bytes_transferred": transfer_result.bytes_transferred,
                "transfer_time": transfer_result.transfer_time,
                "errors": transfer_result.errors,
            }
        except Exception as e:
            await manager.broadcast_build_progress({
                "type": "deploy_error",
                "project": project_name,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }, project_name)
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/projects/{project_name}/config")
    async def get_project_config(project_name: str):
        """Get project congiguration."""
        project = project_manager.get_project(project_name)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        config_path = Path(project.path) / "esp32_config.json"
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        else:
            config = {
                "build_settings": {
                    "optimization_level": 2,
                    "debug_mode": False,
                    "custom_scripts": []
                },
                "deployment_settings": {
                    "auto_deploy": False,
                    "backup_before_deploy": True,
                    "target_devices": []
                },
                "dependencies": []
            }

        return {"config": config}

    @app.put("/api/projects/{project_name}/config")
    async def update_project_config(project_name: str, config: ProjectConfig):
        """Update project congiguration."""
        project = project_manager.get_project(project_name)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        config_path = Path(project.path) / "esp32_config.json"
        config_data = {
            "build_settings": config.build_settings,
            "deploy_settings": config.deployment_settings,
            "dependencies": config.dependencies,
        }

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                json.dump(config_path, f, indent=2)
            return {"success": True}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save config: {str(e)}")

    @app.post("/api/build/{project_name}")
    async def build_project(project_name: str):
        """Start a build for the given project with real-time progress.."""
        project = project_manager.get_project(project_name)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Send build start notification
        await manager.broadcast_build_progress({
            "type": "build_start",
            "project": project_name,
            "timestamp": datetime.now().isoformat()
        }, project_name)

        try:
            result = build_manager.build_project(project)

            # Send build completion notification
            await manager.broadcast_build_progress({
                "type": "build_complete",
                "project": project_name,
                "success": result.success,
                "timestamp": datetime.now().isoformat()
            }, project_name)
            return {
                "success": result.success,
                "files_processed": result.files_processed,
                "total_size": result.total_size,
                "build_time": result.build_time,
                "warnings": result.warnings,
                "errors": result.errors,
            }
        except Exception as e:
            await manager.broadcast_build_progress({
                "type": "build_error",
                "project": project_name,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }, project_name)
            raise HTTPException(status_code=500, detail=str(e))

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
        devices = []
        for d in device_manager.get_devices():
            device_dict = d.to_dict()
            device_dict["last_seen"] = datetime.now().isoformat()
            devices.append(device_dict)
        return {"devices": devices}

    @app.post("/api/devices/scan")
    async def scan_devices():
        """Scan for new ESP32 devices."""
        try:
            device_manager.scan_devices()
            devices = [d.to_dict() for d in device_manager.get_devices()]
            return {"success": True, "devices": devices}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/devices/{port}/info")
    async def get_device_info(port: str):
        """Get detailed device information."""
        device = device_manager.get_device(port)  # Assuming this method exists
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")

        return {
            "device": device.to_dict(),
            "system_info": device_manager.get_device_system_info(port),
            "memory_info": device_manager.get_device_memory_info(port)
        }

    @app.post("/api/devices/{port}/reset")
    async def reset_device(port: str):
        """Reset the ESP32 device."""
        try:
            result = device_manager.reset_device(port)
            return {"success": True}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/system/status")
    async def get_system_status():
        """Get system health and resource information."""
        import psutil

        return {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage("/").percent,
            "active_projects": len(project_manager.list_projects()),
            "connected_devices": len(device_manager.get_devices()),
            "uptime": datetime.now().isoformat()
        }

    @app.get("/api/build-queue")
    async def get_build_queue():
        """Get current build queue status."""
        # This would requre implementing build queue system
        return {"queue": [], "active_builds": 0}

    return app