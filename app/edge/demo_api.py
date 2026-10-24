"""Optional loopback-only edge observation and transient image processing API."""
from __future__ import annotations

import asyncio
import json
import threading

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse
import uvicorn

ALLOWED_ORIGINS = [f'http://{host}:{port}' for host in ('localhost', '127.0.0.1') for port in (8000, 5173)]
MAX_IMAGE_BYTES = 5 * 1024 * 1024


async def read_bounded(request: Request, maximum: int) -> bytes:
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > maximum:
            raise HTTPException(413, 'Request body is too large')
        body.extend(chunk)
    return bytes(body)


def create_demo_app(service):
    if service.demo is None:
        raise ValueError('The demo interface must be explicitly enabled')
    app = FastAPI(title='Forge local demo interface', docs_url=None, redoc_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['localhost', '127.0.0.1', '[::1]', 'testserver'])
    app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_methods=['GET', 'POST'],
                       allow_headers=['Content-Type'], allow_credentials=False)
    image_slot = threading.BoundedSemaphore(1)
    command_slot = threading.Lock()

    @app.middleware('http')
    async def restrict_origin(request, call_next):
        origin = request.headers.get('origin')
        if origin is not None and origin not in ALLOWED_ORIGINS:
            return JSONResponse({'detail': 'Only the local Forge browser origins are allowed'}, status_code=403)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        return response

    async def control_body(request):
        try:
            body = json.loads(await read_bounded(request, 2048))
        except (ValueError, UnicodeDecodeError):
            raise HTTPException(400, 'Expected a JSON object')
        if not isinstance(body, dict):
            raise HTTPException(400, 'Expected a JSON object')
        return body

    def command(action):
        with command_slot:
            try:
                return action()
            except RuntimeError as error:
                raise HTTPException(409, str(error))
            except ValueError as error:
                raise HTTPException(400, str(error))

    @app.get('/api/demo/status')
    def status():
        return service.demo.snapshot()

    @app.post('/api/demo/run')
    async def run(request: Request):
        body = await control_body(request)
        return await asyncio.to_thread(command, lambda: service.demo.start_run(body.get('offline_seconds', 10)))

    @app.post('/api/demo/sync')
    async def sync(request: Request):
        body = await control_body(request)
        if type(body.get('paused')) is not bool:
            raise HTTPException(400, 'paused must be a boolean')
        return await asyncio.to_thread(command, lambda: service.demo.set_paused(body['paused']))

    @app.post('/api/demo/reset')
    async def reset():
        return await asyncio.to_thread(command, service.demo.reset)

    @app.post('/api/demo/privacy')
    async def privacy(request: Request, mode: str = 'blur'):
        if mode not in ('blur', 'mask'):
            raise HTTPException(400, 'mode must be blur or mask')
        if not image_slot.acquire(blocking=False):
            raise HTTPException(429, 'A privacy preview is already processing')
        try:
            body = await read_bounded(request, MAX_IMAGE_BYTES)
        except BaseException:
            image_slot.release()
            raise

        def process():
            try:
                from app.edge.privacy_preview import process_privacy_preview
                return process_privacy_preview(body, mode)
            except ValueError as error:
                raise HTTPException(400, str(error))
            finally:
                image_slot.release()
        return await asyncio.shield(asyncio.to_thread(process))

    return app


def start_demo_server(service, port):
    server = uvicorn.Server(uvicorn.Config(create_demo_app(service), host='127.0.0.1', port=port,
                                           log_level='warning', access_log=False))
    thread = threading.Thread(target=server.run, daemon=True, name='edge-demo-api')
    thread.start()
    return server, thread
