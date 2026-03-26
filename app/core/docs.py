import json
import os
import secrets as secrets_mod

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from app.config import settings

_is_production = os.getenv("ENVIRONMENT", "development").lower() == "production"


def _is_docs_key_valid(key: str | None = None) -> bool:
    """Check if documentation access key is valid. Returns True if access allowed."""
    if not _is_production or not settings.docs_api_key:
        return True
    return key is not None and secrets_mod.compare_digest(key, settings.docs_api_key)


def _docs_gate_page(target: str = "/redoc") -> HTMLResponse:
    """Branded access gate page matching SmilePreview design language."""
    return HTMLResponse("""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>SmilePreview API Documentation</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            background: linear-gradient(135deg, #1e40af 0%, #2563eb 25%, #3b82f6 50%, #06b6d4 75%, #10b981 100%);
            overflow: hidden;
            position: relative;
        }

        body::before {
            content: '';
            position: absolute;
            top: -50%; left: -50%;
            width: 200%; height: 200%;
            background: radial-gradient(circle at 30% 40%, rgba(255,255,255,0.06) 0%, transparent 50%),
                        radial-gradient(circle at 70% 60%, rgba(255,255,255,0.04) 0%, transparent 50%);
            animation: drift 20s ease-in-out infinite;
        }

        @keyframes drift {
            0%, 100% { transform: translate(0, 0) rotate(0deg); }
            50% { transform: translate(-2%, 2%) rotate(1deg); }
        }

        .card {
            position: relative;
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(20px);
            border-radius: 24px;
            padding: 48px 40px;
            width: 100%;
            max-width: 420px;
            box-shadow: 0 25px 60px rgba(0, 0, 0, 0.15), 0 0 0 1px rgba(255, 255, 255, 0.2);
            text-align: center;
            animation: slideUp 0.6s ease-out;
        }

        @keyframes slideUp {
            from { opacity: 0; transform: translateY(30px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .logo {
            margin-bottom: 8px;
            font-size: 32px;
            font-weight: 800;
            color: #1e40af;
            letter-spacing: -0.5px;
        }

        .logo span { color: #10b981; }

        .subtitle {
            font-size: 14px;
            font-weight: 500;
            color: #6B7280;
            margin-bottom: 36px;
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }

        .input-group {
            position: relative;
            margin-bottom: 20px;
        }

        .input-group input {
            width: 100%;
            padding: 16px 20px 16px 48px;
            font-family: 'Inter', sans-serif;
            font-size: 16px;
            font-weight: 500;
            border: 2px solid #E5E7EB;
            border-radius: 14px;
            outline: none;
            transition: all 0.25s ease;
            background: #FAFAFA;
            color: #1F2937;
        }

        .input-group input:focus {
            border-color: #2563eb;
            background: #fff;
            box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.1);
        }

        .input-group input::placeholder {
            color: #9CA3AF;
            font-weight: 400;
        }

        .input-icon {
            position: absolute;
            left: 16px;
            top: 50%;
            transform: translateY(-50%);
            width: 20px;
            height: 20px;
            color: #9CA3AF;
            transition: color 0.25s ease;
        }

        .input-group input:focus ~ .input-icon { color: #2563eb; }

        .btn {
            width: 100%;
            padding: 16px;
            font-family: 'Inter', sans-serif;
            font-size: 16px;
            font-weight: 600;
            color: #fff;
            background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
            border: none;
            border-radius: 14px;
            cursor: pointer;
            transition: all 0.25s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }

        .btn:hover {
            transform: translateY(-1px);
            box-shadow: 0 8px 24px rgba(37, 99, 235, 0.35);
        }

        .btn:active { transform: translateY(0); }

        .btn svg {
            width: 18px; height: 18px;
            transition: transform 0.25s ease;
        }
        .btn:hover svg { transform: translateX(3px); }

        .error-msg {
            color: #DC2626;
            font-size: 13px;
            font-weight: 500;
            margin-top: 12px;
            display: none;
            animation: shake 0.4s ease;
        }

        @keyframes shake {
            0%, 100% { transform: translateX(0); }
            25% { transform: translateX(-6px); }
            75% { transform: translateX(6px); }
        }

        .footer {
            margin-top: 32px;
            padding-top: 24px;
            border-top: 1px solid #F3F4F6;
            font-size: 13px;
            color: #9CA3AF;
        }

        .footer a {
            color: #2563eb;
            text-decoration: none;
            font-weight: 500;
        }
        .footer a:hover { text-decoration: underline; }

        @media (max-width: 480px) {
            .card { margin: 16px; padding: 36px 24px; }
        }
    </style>
</head>
<body>
    <div class="card">
        <div class="logo">Smile<span>Preview</span></div>
        <div class="subtitle">API Documentation</div>

        <form id="keyForm" onsubmit="return submitKey()">
            <div class="input-group">
                <input
                    type="password"
                    id="keyInput"
                    placeholder="Enter access key"
                    autocomplete="off"
                    autofocus
                />
                <svg class="input-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                    <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                </svg>
            </div>
            <button type="submit" class="btn">
                View Documentation
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M5 12h14M12 5l7 7-7 7"/>
                </svg>
            </button>
            <div class="error-msg" id="errorMsg">Invalid access key. Please try again.</div>
        </form>

        <div class="footer">
            Need access? Contact your team lead or visit
            <a href="https://smilepreview.com">smilepreview.com</a>
        </div>
    </div>

    <script>
        const TARGET = """ + json.dumps(target) + """;

        function submitKey() {
            const key = document.getElementById('keyInput').value.trim();
            if (!key) {
                showError();
                return false;
            }
            window.location.href = TARGET + '?key=' + encodeURIComponent(key);
            return false;
        }

        function showError() {
            const el = document.getElementById('errorMsg');
            el.style.display = 'block';
            document.getElementById('keyInput').style.borderColor = '#DC2626';
            setTimeout(() => {
                el.style.display = 'none';
                document.getElementById('keyInput').style.borderColor = '#E5E7EB';
            }, 3000);
        }

        const params = new URLSearchParams(window.location.search);
        if (params.has('key')) { showError(); }
    </script>
</body>
</html>
""", status_code=200)


def register_docs_routes(app: FastAPI) -> None:
    """Register documentation-related routes on the FastAPI application."""

    @app.get("/openapi.json", include_in_schema=False)
    async def get_openapi_schema(key: str | None = None):
        """Serve OpenAPI schema, protected by key in production."""
        if not _is_docs_key_valid(key):
            raise HTTPException(
                status_code=403,
                detail="Invalid or missing documentation access key.",
            )
        return JSONResponse(content=app.openapi())

    @app.get("/redoc", response_class=HTMLResponse, include_in_schema=False)
    async def custom_redoc(key: str | None = None):
        """Custom ReDoc documentation with SmilePreview branding."""
        if not _is_docs_key_valid(key):
            return _docs_gate_page("/redoc")
        key_param = f"?key={key}" if key else ""
        return HTMLResponse(f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>SmilePreview API Documentation</title>
        <meta charset="utf-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>
            body {{ margin: 0; padding: 0; }}
        </style>
    </head>
    <body>
        <div id="redoc-container"></div>
        <script src="https://cdn.jsdelivr.net/npm/redoc@2.1.3/bundles/redoc.standalone.js"></script>
        <script>
            Redoc.init('/openapi.json{key_param}', {{
                theme: {{
                    colors: {{
                        primary: {{ main: '#2563eb' }},
                    }},
                    typography: {{
                        fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
                        headings: {{ fontFamily: "'Inter', sans-serif" }},
                    }},
                    sidebar: {{
                        backgroundColor: '#f8fafc',
                        textColor: '#334155',
                    }},
                    rightPanel: {{
                        backgroundColor: '#1e293b',
                    }},
                }},
                hideDownloadButton: false,
                expandResponses: '200',
            }}, document.getElementById('redoc-container'));
        </script>
    </body>
    </html>
        """)

    @app.get("/docs", response_class=HTMLResponse, include_in_schema=False)
    async def custom_docs_redirect(key: str | None = None):
        """Redirect to custom ReDoc documentation."""
        if not _is_docs_key_valid(key):
            return _docs_gate_page("/redoc")
        key_param = f"?key={key}" if key else ""
        return HTMLResponse(f"""
    <script>
        window.location.href = '/redoc{key_param}';
    </script>
        """, status_code=302)
