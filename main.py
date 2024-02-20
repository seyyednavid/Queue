# 12/01/2024
# This version works fine with opencv and websocket
# issue1: The player doesn't play sound because of opencv (should be changed to sth like vlc)
# issue2: Terminating the threads and the code wasn't handled and the visual studio code needs to be closed


from flask import Flask, render_template, redirect, request, url_for
from flask_sqlalchemy import SQLAlchemy
import asyncio
import websockets
import json
import threading
import webbrowser
import subprocess
import pyautogui
import time

app = Flask(__name__, static_folder='static')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'  
db = SQLAlchemy(app)

# Variable to store number of cashiers (0-23)
called_position = 0

# Define the dictionary mapping keys to video filenames
video_files = {"1": "1.mp4", "2": "2.mp4", "3": "3.mp4", "4": "4.mp4", "5": "5.mp4", "6": "6.mp4", 
               "7": "7.mp4", "8": "8.mp4",
               "9": "9.mp4", "10": "10.mp4", "11": "11.mp4", "12": "12.mp4", "13": "13.mp4", "14": "14.mp4", "15": "15.mp4", "16": "16.mp4",
               "17": "17.mp4", "18": "18.mp4", "19": "19.mp4", "20": "20.mp4", "21": "21.mp4", "22": "22.mp4", "23": "23.mp4", "24": "24.mp4",
                "background": "background.mp4"}


class Settings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    flashspeededgelit = db.Column(db.String(10))
    numofflashes = db.Column(db.String(10))
    on_color = db.Column(db.String(10))
    off_color = db.Column(db.String(10))
    free_color = db.Column(db.String(10))
    busy_color = db.Column(db.String(10))

# Store a set of connected websocket clients
connected_clients = set()

# Convert hex color to a tuple (red, Green, Blue)
async def hex_to_rgb(hex):
    return tuple(int(hex[i:i+2], 16) for i in (1, 3, 5))

# Receive the message from websocket and response back
async def handle_client(websocket, path):

    global called_position
    # Add the client to the set of connected clients
    connected_clients.add(websocket)
    print(f"New client connected. Total clients: {len(connected_clients)}")

    try:
        while True:
            message_json = await websocket.recv()  # Wait for a message from the client

            if message_json:
                # Parse JSON message
                try:
                    message_data = json.loads(message_json)
                    print(message_data)

                    if message_data["ws_id"] == "Tensator_Websocket_server":
                        if message_data["cb_id"] == "CB_123456789":
                            if message_data["device_type"] == "Edgelit-button":
                                egdelit_id = int(message_data["cmd_info"]["target"])
                                called_position = egdelit_id
                                event = message_data["cmd_info"]["event"]

                                with app.app_context():
                                    data_in_db = Settings.query.filter_by(id=egdelit_id).first()

                                    if data_in_db:
                                        message_data["cmd_info"]["flash_speed"] = int(data_in_db.flashspeededgelit)
                                        message_data["cmd_info"]["no_of_flashes"] = int(data_in_db.numofflashes)
                                        message_data["cmd_info"]["on_color"] = await hex_to_rgb(data_in_db.on_color)
                                        message_data["cmd_info"]["off_color"] = await hex_to_rgb(data_in_db.off_color)
                                        message_data["cmd_info"]["free_color"] = await hex_to_rgb(data_in_db.free_color)
                                        message_data["cmd_info"]["busy_color"] = await hex_to_rgb(data_in_db.busy_color)
                                        print(f"\nthe message prepared to be sent: {message_data}\n")
                                        # await websocket.send(json.dumps(message_data))
                                        # Update called_position for all connected clients
                                        for client in connected_clients:
                                            await client.send(json.dumps(message_data))
                                    else:
                                        print(f"No data found in the database for edgelit_id: {egdelit_id}")
                            else:
                                print("type mismatch")
                        else:
                            print("cb_id mismatch")
                    else:
                        print("ws_id mismatch")

                except json.JSONDecodeError:
                    print("Error decoding JSON message")

    except websockets.exceptions.ConnectionClosed:
        connected_clients.remove(websocket)
        print(f"Client {websocket} disconnected. Total clients: {len(connected_clients)}")

# Manages the websocket server thread
class WebSocketServerThread(threading.Thread):
    def __init__(self):
        super().__init__()
        self.running = True
        self.server = None  # Add a variable to store the server instance
        self.serve_forever_task = None  # Add a variable to store the serve_forever task

    def terminate(self):
        self.running = False
        if self.server:
            self.server.close()  # Close the server
            asyncio.run_coroutine_threadsafe(self.serve_forever_task.cancel(), asyncio.get_event_loop())
            asyncio.get_event_loop().run_until_complete(self.server.wait_closed())  # Wait for server to close

    def run(self):
        while self.running:
            asyncio.set_event_loop(asyncio.new_event_loop())
            self.server = websockets.serve(handle_client, "127.0.0.1", 8764)
            self.serve_forever_task = asyncio.ensure_future(self.server)
            asyncio.get_event_loop().run_until_complete(self.serve_forever_task)
            asyncio.get_event_loop().run_forever()



# Main route Flask server decorator
@app.route("/")
def main():
    return render_template("index.html")

# Edgeled settings flask server decorator
@app.route("/settings", methods=["POST", "GET"])
def edgelit_save():
    if request.method == "GET":
        edgeled_settings = {
            'flashspeededgelit': [],
            'numofflashes': [],
            'on_color': [],
            'off_color': [],
            'free_color': [],
            'busy_color': []
        }

        for i in range(1, 24):
            data_in_db = Settings.query.filter_by(id=i).first()

            if data_in_db:
                edgeled_settings['flashspeededgelit'].append(data_in_db.flashspeededgelit)
                edgeled_settings['numofflashes'].append(data_in_db.numofflashes)
                edgeled_settings['on_color'].append(data_in_db.on_color)
                edgeled_settings['off_color'].append(data_in_db.off_color)
                edgeled_settings['free_color'].append(data_in_db.free_color)
                edgeled_settings['busy_color'].append(data_in_db.busy_color)
        # Get the whole info from db and show them into Server_page.html page
        return render_template("Server_page.html", edgeled_settings=edgeled_settings)
    elif request.method == "POST":
        form_data = request.form

        for i in range(1, 24):
            existing_setting = Settings.query.filter_by(id=i).first()

            if existing_setting:
                existing_setting.flashspeededgelit = form_data[f'flashspeededgelit{i}']
                existing_setting.numofflashes = form_data[f'numofflashes{i}']
                existing_setting.on_color = form_data[f'on_color{i}']
                existing_setting.off_color = form_data[f'off_color{i}']
                existing_setting.free_color = form_data[f'free_color{i}']
                existing_setting.busy_color = form_data[f'busy_color{i}']
            else:
                new_setting = Settings(
                    flashspeededgelit=form_data[f'flashspeededgelit{i}'],
                    numofflashes=form_data[f'numofflashes{i}'],
                    on_color=form_data[f'on_color{i}'],
                    off_color=form_data[f'off_color{i}'],
                    free_color=form_data[f'free_color{i}'],
                    busy_color=form_data[f'busy_color{i}']
                )
                db.session.add(new_setting)

        db.session.commit()

        return redirect(url_for('main'))

@app.route('/callforward')
def call_forward():
    # Render the template and pass the dictionary of video filenames
    return render_template('callforward.html', video_files=video_files, position=called_position)


def open_browser():
    # Open the default web browser with the home page
    webbrowser.open('http://127.0.0.1:8888/callforward')
    time.sleep(2)
    # Simulate pressing the F11 key to enter fullscreen mode
    pyautogui.press('f11')
    
    
# Main code
if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    # Start the WebSocket thread
    websocket_thread = WebSocketServerThread()
    websocket_thread.start()

    # Run the Flask app
    open_browser()
    app.run(host="127.0.0.1", port=8888, debug=True, use_reloader=False)

    # Wait for threads to finish
    websocket_thread.join()





