#!/usr/bin/env python3
"""
Simple local server for editing JSON files directly.
Usage: python json-viewer-server.py [filename]
Default: tmp_lh_links.json
"""

import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Get filename from command line or use default
JSON_FILE = sys.argv[1] if len(sys.argv) > 1 else 'tmp_lh_links.json'

class JSONEditorHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/':
            # Serve the HTML viewer
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            with open('json-viewer.html', 'r', encoding='utf-8') as f:
                html = f.read()
                # Inject the filename into the page
                html = html.replace('let currentFileName = \'\';', f'let currentFileName = \'{JSON_FILE}\';')
                self.wfile.write(html.encode('utf-8'))
        
        elif parsed_path.path == '/data':
            # Serve the JSON data
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            try:
                with open(JSON_FILE, 'r', encoding='utf-8') as f:
                    self.wfile.write(f.read().encode('utf-8'))
            except FileNotFoundError:
                self.wfile.write(json.dumps({'error': 'File not found'}).encode('utf-8'))
        
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        if self.path == '/save':
            # Save the JSON data
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                # Validate JSON
                data = json.loads(post_data.decode('utf-8'))
                
                # Create backup
                if os.path.exists(JSON_FILE):
                    backup_file = JSON_FILE + '.backup'
                    with open(JSON_FILE, 'r', encoding='utf-8') as f:
                        with open(backup_file, 'w', encoding='utf-8') as bf:
                            bf.write(f.read())
                
                # Write new data
                with open(JSON_FILE, 'w', encoding='utf-8') as f:
                    f.write(json.dumps(data, ensure_ascii=False, indent=2))
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'success', 'message': 'File saved'}).encode('utf-8'))
            
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'error', 'message': str(e)}).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_OPTIONS(self):
        # Handle CORS preflight
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def log_message(self, format, *args):
        # Suppress default logging or customize it
        print(f"[{self.date_time_string()}] {format % args}")

def run_server(port=8000):
    server_address = ('', port)
    httpd = HTTPServer(server_address, JSONEditorHandler)
    print(f"\n✅ Server started!")
    print(f"📂 Editing file: {JSON_FILE}")
    print(f"🌐 Open in browser: http://localhost:{port}")
    print(f"💾 Changes will save directly to {JSON_FILE}")
    print(f"🔄 Backups saved to {JSON_FILE}.backup")
    print(f"\n⌨️  Press Ctrl+C to stop the server\n")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped")
        httpd.shutdown()

if __name__ == '__main__':
    # Check if JSON file exists
    if not os.path.exists(JSON_FILE):
        print(f"❌ Error: File '{JSON_FILE}' not found!")
        sys.exit(1)
    
    # Check if HTML file exists
    if not os.path.exists('json-viewer.html'):
        print(f"❌ Error: 'json-viewer.html' not found!")
        sys.exit(1)
    
    run_server()
