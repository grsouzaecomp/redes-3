import sqlite3
from flask import Flask, request, jsonify
import bcrypt
import threading
import asyncio
import websockets
import json
import requests

app = Flask(__name__)

# Configuração do Banco de Dados
DB_NAME = "server2.db"  # Altere para server2.db ou server3.db nos outros servidores
PORT = 5001  # Altere para 5001 ou 5002
WS_PORT = 8001  # Porta para WebSocket (altere para 8001 ou 8002 nos outros servidores)

# Lista de outros servidores WebSocket
# URLs HTTP dos servidores para comunicação REST
other_http_servers = [
    "http://localhost:5000",
    "http://localhost:5002"
]

# URLs WebSocket para sincronização em tempo real
other_ws_servers = [
    "ws://localhost:8000",
    "ws://localhost:8002"
]

# Lista de conexões WebSocket ativas
active_connections = set()

# Inicialização do Banco de Dados
def setup_database():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT UNIQUE NOT NULL,
      password TEXT NOT NULL,
      balance REAL DEFAULT 0
    )
  """)
  cursor.execute("""
    CREATE TABLE IF NOT EXISTS events (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      event_id TEXT UNIQUE NOT NULL,
      odds TEXT NOT NULL
    )
  """)
  cursor.execute("""
    CREATE TABLE IF NOT EXISTS bets (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      event_id TEXT NOT NULL,
      bet_option TEXT NOT NULL,
      amount REAL NOT NULL,
      FOREIGN KEY (user_id) REFERENCES users(id)
    )
  """)
  conn.commit()
  conn.close()

setup_database()

# Funções Auxiliares para Banco de Dados
def execute_query(query, params=(), fetch_one=False, fetch_all=False):
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute(query, params)
  result = None
  if fetch_one:
    result = cursor.fetchone()
  elif fetch_all:
    result = cursor.fetchall()
  conn.commit()
  conn.close()
  return result

# Funções de WebSocket
async def send_to_all(message):
  """Envia uma mensagem a todos os servidores conectados via WebSocket."""
  for ws in active_connections:
    try:
      await ws.send(message)
    except Exception as e:
      print(f"Erro ao enviar mensagem via WebSocket: {e}")

async def websocket_server(websocket, path):
  """Gerencia conexões WebSocket recebidas."""
  print("Nova conexão WebSocket")
  active_connections.add(websocket)
  try:
    async for message in websocket:
      data = json.loads(message)
      process_ws_message(data)  # Processa as mensagens recebidas
  
  except Exception as e:
    print(f"Erro na conexão WebSocket: {e}")
  
  finally:
    active_connections.remove(websocket)

def process_ws_message(data):
  """Processa mensagens recebidas via WebSocket."""
  if data["type"] == "user":
    sync_users([data["data"]])
  elif data["type"] == "event":
    sync_events([data["data"]])
  elif data["type"] == "bet":
    sync_bets([data["data"]])
  else:
    print(f"Tipo de mensagem desconhecido: {data['type']}")

# Funções de Sincronização
def sync_users(users):
  for user in users:
    existing_user = execute_query(
      "SELECT id FROM users WHERE username = ?",
      (user["username"],),
      fetch_one=True
    )
    if not existing_user:
      execute_query(
        """
        INSERT INTO users (username, password, balance)
        VALUES (?, ?, ?)
        """,
        (user["username"], user["password"], user["balance"])
      )


def sync_events(events):
  """Sincroniza eventos recebidos."""
  for event in events:
    try:
      execute_query(
        """
        INSERT OR IGNORE INTO events (event_id, odds)
        VALUES (?, ?)
        """,
        (event["event_id"], str(event["odds"]))
      )
      print(f"Evento sincronizado: {event}")
    
    except Exception as e:
      print(f"Erro ao sincronizar evento: {e}")


def sync_bets(bets):
  for bet in bets:
    execute_query(
      """
      INSERT OR IGNORE INTO bets (id, user_id, event_id, bet_option, amount)
      VALUES (?, ?, ?, ?, ?)
      """,
      (bet["id"], bet["user_id"], bet["event_id"], bet["bet_option"], bet["amount"])
    )

# Propagação de Mudanças
def propagate_change(change_type, data):
  """Propaga mudanças via WebSocket."""
  message = json.dumps({"type": change_type, "data": data})
  asyncio.run(send_to_all(message))
  print(f"Propagando mudança: {message}")


# Endpoints REST
@app.route('/register', methods=['POST'])
def register():
  data = request.json
  username = data["username"]
  password = data["password"]

  # Verificar se o usuário já existe localmente
  existing_user = execute_query(
    "SELECT id FROM users WHERE username = ?",
    (username,),
    fetch_one=True
  )
  if existing_user:
    return jsonify({"error": "Usuário já existe"}), 400

  # Verificar se o usuário existe em outros servidores usando HTTP
  for server in other_http_servers:
    try:
      response = requests.get(f"{server}/check_user/{username}")
      if response.status_code == 200:
        return jsonify({"error": "Usuário já existe em outro servidor"}), 400
    except Exception as e:
      print(f"Erro ao verificar no servidor {server}: {e}")

  # Criar um novo registro de usuário
  hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
  try:
    execute_query(
      "INSERT INTO users (username, password, balance) VALUES (?, ?, ?)",
      (username, hashed_password, 0)
    )
    # Propagar para outros servidores via WebSocket
    propagate_change("user", {"username": username, "password": hashed_password.decode('utf-8'), "balance": 0})
    return jsonify({"message": "Registro realizado com sucesso!"}), 200
  
  except Exception as e:
    print(f"Erro ao registrar usuário: {e}")
    return jsonify({"error": "Erro interno do servidor"}), 500


@app.route('/check_user/<username>', methods=['GET'])
def check_user(username):
  user = execute_query(
    "SELECT id FROM users WHERE username = ?",
    (username,),
    fetch_one=True
  )
  if user:
    return jsonify({"exists": True}), 200
  return jsonify({"exists": False}), 404

@app.route('/login', methods=['POST'])
def login():
  data = request.json
  username = data["username"]
  password = data["password"]

  user = execute_query(
    "SELECT id, password FROM users WHERE username = ?",
    (username,),
    fetch_one=True
  )

  if not user:
    return jsonify({"error": "Usuário não encontrado"}), 404

  user_id, hashed_password = user
  if bcrypt.checkpw(password.encode('utf-8'), hashed_password):
    return jsonify({"message": "Login realizado com sucesso!"}), 200
  else:
    return jsonify({"error": "Senha incorreta"}), 401

# Adicione endpoints semelhantes para /create_event, /place_bet, e outros, com chamadas para `propagate_change`.
@app.route('/balance/<username>', methods=['GET'])
def get_balance(username):
    user = execute_query(
        "SELECT balance FROM users WHERE username = ?",
        (username,),
        fetch_one=True
    )
    if user:
        return jsonify({"balance": user[0]}), 200
    return jsonify({"error": "Usuário não encontrado"}), 404

# Inicialização do WebSocket
def start_websocket_server():
    """Inicia o servidor WebSocket."""
    async def run_server():
        start_server = websockets.serve(websocket_server, "localhost", WS_PORT)
        print(f"Servidor WebSocket iniciado em ws://localhost:{WS_PORT}")
        await start_server  # Aguarda o servidor ser executado

    asyncio.run(run_server())  # Inicia o loop de eventos

@app.route('/deposit', methods=['POST'])
def deposit():
  data = request.json
  username = data["username"]
  amount = data["amount"]

  user = execute_query(
    "SELECT id FROM users WHERE username = ?",
    (username,),
    fetch_one=True
  )

  if not user:
    return jsonify({"error": "Usuário não encontrado"}), 404

  user_id = user[0]
  execute_query(
    "UPDATE users SET balance = balance + ? WHERE id = ?",
    (amount, user_id)
  ) 
  return jsonify({"message": f"Depósito de {amount} realizado com sucesso!"}), 200

@app.route('/create_event', methods=['POST'])
def create_event():
  data = request.json
  event_id = data["event_id"]
  odds = data["odds"]

  try:
    # Inserir evento no banco local
    execute_query(
      "INSERT INTO events (event_id, odds) VALUES (?, ?)",
      (event_id, str(odds))
    )
    # Propagar o evento para outros servidores
    propagate_change("event", {"event_id": event_id, "odds": odds})
    return jsonify({"message": f"Evento {event_id} criado com sucesso!"}), 200
  
  except sqlite3.IntegrityError:
    return jsonify({"error": "Evento já existe"}), 400
  
  except Exception as e:
    print(f"Erro interno ao criar evento: {e}")
    return jsonify({"error": "Erro interno do servidor"}), 500


@app.route('/list_events', methods=['GET'])
def list_events():
  # Consultar eventos locais
  local_events = execute_query("SELECT event_id, odds FROM events", fetch_all=True)
  events = [{"event_id": e[0], "odds": eval(e[1])} for e in local_events]

  # Consultar eventos de outros servidores
  for server in other_http_servers:
    try:
      response = requests.get(f"{server}/local_events")
      if response.status_code == 200:
        remote_events = response.json()
        events.extend(remote_events)
    except Exception as e:
      print(f"Erro ao consultar eventos no servidor {server}: {e}")

  # Remover duplicatas (mesmo evento_id)
  unique_events = {event["event_id"]: event for event in events}
  return jsonify(list(unique_events.values())), 200

@app.route('/local_events', methods=['GET'])
def local_events():
  events = execute_query("SELECT event_id, odds FROM events", fetch_all=True)
  if events:
    return jsonify([{"event_id": e[0], "odds": eval(e[1])} for e in events]), 200
  return jsonify([]), 200


@app.route('/place_bet', methods=['POST'])
def place_bet():
  data = request.json
  username = data["username"]
  event_id = data["event_id"]
  bet_option = data["bet_option"]
  amount = data["amount"]

  # Verificar se o usuário existe
  user = execute_query("SELECT id, balance FROM users WHERE username = ?", (username,), fetch_one=True)
  if not user:
    return jsonify({"error": "Usuário não encontrado"}), 404

  user_id, balance = user

  # Verificar saldo suficiente
  if balance < amount:
    return jsonify({"error": "Saldo insuficiente"}), 400

  # Verificar se o evento existe
  event = execute_query("SELECT id, odds FROM events WHERE event_id = ?", (event_id,), fetch_one=True)
  if not event:
    return jsonify({"error": "Evento não encontrado"}), 404

  event_id_db, odds = event

  # Registrar a aposta
  try:
    execute_query(
      "INSERT INTO bets (user_id, event_id, bet_option, amount) VALUES (?, ?, ?, ?)",
      (user_id, event_id_db, bet_option, amount)
    )
    # Atualizar o saldo do usuário
    execute_query("UPDATE users SET balance = balance - ? WHERE id = ?", (amount, user_id))
    return jsonify({"message": "Aposta realizada com sucesso!"}), 200
  
  except Exception as e:
    print(f"Erro interno ao registrar aposta: {e}")
    return jsonify({"error": "Erro interno do servidor"}), 500

# Inicializar Servidor
if __name__ == '__main__':
    threading.Thread(target=start_websocket_server, daemon=True).start()  # WebSocket
    print(f"Servidor HTTP iniciado em http://localhost:{PORT}")
    app.run(port=PORT)  # Flask
