@echo off
rem Music Video Studio: build the UI once (or after updates), then run the server on http://localhost:8000
cd /d "%~dp0"
if not exist frontend\node_modules ( pushd frontend & call npm install & popd )
if not exist renderer\node_modules ( pushd renderer & call npm install & popd )
if not exist frontend\dist\index.html ( pushd frontend & call npm run build & popd )
start "" http://localhost:8000
uv run studio
