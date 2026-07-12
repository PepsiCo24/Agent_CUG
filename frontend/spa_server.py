import http.server
import os
import sys
import mimetypes

PORT = 4173
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dist')

class SPAHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def do_GET(self):
        path = self.translate_path(self.path)
        # If the requested file doesn't exist, serve index.html (SPA fallback)
        if not os.path.exists(path) or os.path.isdir(path):
            self.path = '/index.html'
        return super().do_GET()

    def log_message(self, format, *args):
        print(f"[SPA] {args[0]}")

if __name__ == '__main__':
    print(f"SPA Server running on http://localhost:{PORT}")
    print(f"Serving: {ROOT}")
    http.server.HTTPServer(('0.0.0.0', PORT), SPAHandler).serve_forever()
