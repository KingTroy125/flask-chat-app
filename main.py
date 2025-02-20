from flask import Flask, render_template, request, session, redirect, url_for, flash
from flask_socketio import SocketIO, join_room, leave_room, send
from flask_session import Session
import os
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SESSION_TYPE'] = 'filesystem'

Session(app)
socketio = SocketIO(app, async_mode=None)  # Remove gevent mode

# Store rooms and messages in memory (use a database in production)
rooms = {}

@app.route('/', methods=['GET', 'POST'])
def index():
    return render_template('index.html')

@app.route('/chat', methods=['GET', 'POST'])
def chat():
    if request.method == 'POST':
        username = request.form.get('username')
        room = request.form.get('room')
        
        if not username or not room:
            flash('Both username and room code are required!')
            return redirect(url_for('index'))
        
        if room not in rooms:
            flash('Room does not exist! Please check the room code.')
            return redirect(url_for('index'))
            
        session['username'] = username
        session['room'] = room
        
        # Add user to the room's member list
        if username not in rooms[room]['members']:
            rooms[room]['members'].append(username)
        
        return render_template('chat.html', 
                             username=username, 
                             room=room,
                             messages=rooms[room]['messages'])
    
    if not session.get('username'):
        return redirect(url_for('index'))
        
    room = session.get('room')
    return render_template('chat.html', 
                         username=session.get('username'), 
                         room=room,
                         room_name=rooms[room].get('name', room))

@app.route('/create-room', methods=['POST'])
def create_room():
    username = request.form.get('username')
    room_name = request.form.get('room_name')
    
    if not username or not room_name:
        return redirect(url_for('index'))
    
    # Generate a unique room code
    room_code = f"{room_name.lower().replace(' ', '-')}-{os.urandom(3).hex()}"
    
    session['username'] = username
    session['room'] = room_code
    
    rooms[room_code] = {
        'name': room_name,
        'members': [],
        'messages': [],
        'created_by': username,
        'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    return render_template('chat.html', 
                         username=username, 
                         room=room_code, 
                         room_name=room_name)

@app.route('/join/<code>', methods=['GET'])
def join_with_code(code):
    if code not in rooms:
        flash('Invalid room code!')
        return redirect(url_for('index'))
    return render_template('join.html', room_code=code, room_name=rooms[code].get('name'))

@socketio.on('connect')
def handle_connect():
    if session.get('username') and session.get('room'):
        join_room(session['room'])
        send({
            'username': 'System',
            'message': f"{session['username']} has joined the room"
        }, to=session['room'])
        rooms[session['room']]['members'].append(session['username'])

@socketio.on('message')
def handle_message(data):
    room = session.get('room')
    if room:
        send({
            'username': session['username'],
            'message': data['message']
        }, to=room)
        rooms[room]['messages'].append({
            'username': session['username'],
            'message': data['message']
        })

@socketio.on('disconnect')
def handle_disconnect():
    room = session.get('room')
    username = session.get('username')
    
    if username and room:
        leave_room(room)
        if username in rooms[room]['members']:
            rooms[room]['members'].remove(username)
        
        send({
            'username': 'System',
            'message': f'{username} has left the room'
        }, to=room)
        
        session.clear()

if __name__ == '__main__':
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)  # Updated run parameters