#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import yaml
import glob
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
import threading
import time
import logging

FILE_PATTERN = "/app/metrics_files/*.metrics"
COPY_INTERVAL = 5  # seconds
COPY_PATH = "/app/metrics_files/final"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

if not os.path.isdir("/app/metrics_files"):
    os.mkdir("/app/metrics_files")

def copy_files():
    while True:
        with open(COPY_PATH, "wb") as outfile:
            for f in glob.glob(FILE_PATTERN):
                with open(f, "rb") as infile:
                    shutil.copyfileobj(infile, outfile)
        time.sleep(COPY_INTERVAL)

# Chargez le fichier de configuration YAML
with open("config.yaml", "r") as yaml_file:
    config = yaml.safe_load(yaml_file)

# Obtenez les valeurs de configuration à partir du fichier YAML
GLOBAL_TIMEOUT = config.get("timeout", 15)
GLOBAL_COMMAND = config.get("command", "bash")
GLOBAL_SLEEP = config.get("sleep", 5)
SCRIPTS = config.get("scripts", {})

def execute_script(script_name, script_config):
    while True:
        timeout = script_config.get("timeout", GLOBAL_TIMEOUT)
        script_path = script_config.get("path")
        script_command = script_config.get("command", GLOBAL_COMMAND)
        logging.info(f"Executing script {script_name}: {script_command} {script_path}")
        try:
            output = subprocess.check_output(
                [script_command, script_path],
                stderr=subprocess.STDOUT,
                timeout=timeout
            )
            logging.info(f"Script {script_name} executed successfully{output.decode()}")
        except subprocess.TimeoutExpired as e:
            if e.output is not None:
                logging.info(f"Script {script_name} timed out after {timeout} seconds: {e.output.decode()}")
            else:
                logging.info(f"Script {script_name} timed out after {timeout} seconds.")
        except subprocess.CalledProcessError as e:
            if e.output is not None:
                logging.info(f"Script {script_name} failed with exit code {e.returncode}: {e.output.decode()}")
            else:
                logging.info(f"Script {script_name} failed with exit code {e.returncode}.")
        
        sleep_interval = script_config.get("sleep", GLOBAL_SLEEP)
        time.sleep(sleep_interval)


def execute_scripts():
    threads = []
    for script_name, script_config in SCRIPTS.items():
        thread = threading.Thread(target=execute_script, args=(script_name, script_config))
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()

class FileHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        with open(COPY_PATH, "rb") as f:
            self.wfile.write(f.read())

if __name__ == "__main__":
    
    copy_thread = threading.Thread(target=copy_files)
    copy_thread.start()

    script_thread = threading.Thread(target=execute_scripts)
    script_thread.start()

    server_address = ("0.0.0.0", 9025)
    logging.info(f"Serveur HTTP en écoute sur {server_address[0]}:{server_address[1]}")
    
    httpd = HTTPServer(server_address, FileHandler)
    httpd.serve_forever()
