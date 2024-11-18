import requests

class BettingClient:
  def __init__(self, server_url):
    self.server_url = server_url
    self.username = None

  def register(self, username, password):
    payload = {"username": username, "password": password}
    response = requests.post(f"{self.server_url}/register", json=payload)
    if response.status_code == 200:
      print("Registro realizado com sucesso!")
    else:
      error_message = response.json().get("error", "Erro desconhecido")
      print(f"Erro ao registrar: {error_message}")


  def login(self, username, password):
    payload = {"username": username, "password": password}
    try:
      response = requests.post(f"{self.server_url}/login", json=payload)
      if response.status_code == 200:
        print("Login realizado com sucesso!")
        self.username = username
      else:
        error_message = response.json().get("error", "Erro desconhecido")
        print(f"Erro ao fazer login: {error_message}")
    
    except requests.exceptions.JSONDecodeError:
      print("Erro: Resposta inválida do servidor. Tente novamente.")


  def deposit(self, amount):
    if not self.username:
      print("Você precisa fazer login primeiro!")
      return

    payload = {"username": self.username, "amount": amount}
    try:
      response = requests.post(f"{self.server_url}/deposit", json=payload)
      if response.status_code == 200:
        print(response.json().get("message", "Depósito realizado com sucesso!"))
      else:
        error_message = response.json().get("error", "Erro desconhecido")
        print(f"Erro ao realizar depósito: {error_message}")
    except requests.exceptions.JSONDecodeError:
      print("Erro: Resposta inválida do servidor. Tente novamente.")


  def check_balance(self):
    if not self.username:
      print("Você precisa fazer login primeiro!")
      return

    try:
      response = requests.get(f"{self.server_url}/balance/{self.username}")
      if response.status_code == 200:
        print(f"Saldo disponível: {response.json().get('balance')}")
      else:
        error_message = response.json().get("error", "Erro desconhecido")
        print(f"Erro ao verificar saldo: {error_message}")
    except requests.exceptions.JSONDecodeError:
      print("Erro: Resposta inválida do servidor. Tente novamente.")


  def create_event(self, event_id, odds):
    payload = {"event_id": event_id, "odds": odds}
    try:
      response = requests.post(f"{self.server_url}/create_event", json=payload)
      if response.status_code == 200:
        print(response.json().get("message", "Evento criado com sucesso!"))
      else:
        error_message = response.json().get("error", "Erro desconhecido")
        print(f"Erro ao criar evento: {error_message}")
    except requests.exceptions.JSONDecodeError:
      print("Erro: Resposta inválida do servidor. Tente novamente.")
    except requests.exceptions.RequestException as e:
      print(f"Erro de conexão com o servidor: {e}")


  def list_events(self):
    try:
      response = requests.get(f"{self.server_url}/list_events")
      if response.status_code == 200:
        events = response.json()
        if events:
          print("Eventos disponíveis:")
          for event in events:
            print(f"ID: {event['event_id']}, Odds: {event['odds']}")
        else:
          print("Nenhum evento disponível no momento.")
      else:
        error_message = response.json().get("error", "Erro desconhecido")
        print(f"Erro ao listar eventos: {error_message}")
        
    except requests.exceptions.JSONDecodeError:
      print("Erro: Resposta inválida do servidor. Tente novamente.")
    
    except requests.exceptions.RequestException as e:
      print(f"Erro de conexão com o servidor: {e}")


  def place_bet(self, event_id, bet_option, amount):
    if not self.username:
      print("Você precisa fazer login primeiro!")
      return

    payload = {
      "username": self.username,
      "event_id": event_id,
      "bet_option": bet_option,
      "amount": amount,
    }

    try:
      response = requests.post(f"{self.server_url}/place_bet", json=payload)
      if response.status_code == 200:
        print(response.json().get("message", "Aposta realizada com sucesso!"))
      else:
        error_message = response.json().get("error", "Erro desconhecido")
        print(f"Erro ao realizar aposta: {error_message}")
    
    except requests.exceptions.JSONDecodeError:
      print("Erro: Resposta inválida do servidor. Tente novamente.")
    
    except requests.exceptions.RequestException as e:
      print(f"Erro de conexão com o servidor: {e}")


  def resolve_event(self, event_id, result):
    payload = {"event_id": event_id, "result": result}
    try:
      response = requests.post(f"{self.server_url}/resolve_event", json=payload)
      if response.status_code == 200:
        print(response.json().get("message", "Evento resolvido com sucesso!"))
      else:
        error_message = response.json().get("error", "Erro desconhecido")
        print(f"Erro ao resolver evento: {error_message}")
    except requests.exceptions.JSONDecodeError:
      print("Erro: Resposta inválida do servidor. Tente novamente.")
    except requests.exceptions.RequestException as e:
      print(f"Erro de conexão com o servidor: {e}")


# Menu do cliente
def main():
  print("Bem-vindo ao Sistema de Apostas!")
  server_url = input("Insira o URL do servidor (ex.: http://localhost:5000): ").strip()
  client = BettingClient(server_url)

  while not client.username:
    print("\nLogin ou Registro:")
    print("1. Registrar")
    print("2. Login")
    print("3. Sair")
    
    choice = input("Escolha uma opção: ").strip()
    if choice == "1":
      username = input("Digite o nome de usuário: ").strip()
      password = input("Digite a senha: ").strip()
      client.register(username, password)
    elif choice == "2":
      username = input("Digite o nome de usuário: ").strip()
      password = input("Digite a senha: ").strip()
      client.login(username, password)
    elif choice == "3":
      print("Saindo do sistema. Até mais!")
      return
    else:
      print("Opção inválida. Tente novamente.")

  while True:
    print("\nMenu:")
    print("1. Verificar Saldo")
    print("2. Depositar")
    print("3. Criar Evento")
    print("4. Listar Eventos")
    print("5. Apostar")
    print("6. Resolver Evento (Admin)")
    print("7. Sair")

    choice = input("Escolha uma opção: ").strip()
    if choice == "1":
      client.check_balance()
    elif choice == "2":
      amount = float(input("Digite o valor do depósito: "))
      client.deposit(amount)
    elif choice == "3":
      event_id = input("Digite o ID do evento: ").strip()
      odds = input("Digite as odds no formato JSON (ex.: {\"heads\": 2.0, \"tails\": 2.0}): ")
      client.create_event(event_id, odds)
    elif choice == "4":
      client.list_events()
    elif choice == "5":
      event_id = input("Digite o ID do evento: ").strip()
      bet_option = input("Digite sua aposta (ex.: heads): ").strip()
      amount = float(input("Digite o valor da aposta: "))
      client.place_bet(event_id, bet_option, amount)
    elif choice == "6":
      event_id = input("Digite o ID do evento: ").strip()
      result = input("Digite o resultado do evento (ex.: heads): ").strip()
      client.resolve_event(event_id, result)
    elif choice == "7":
      print("Saindo do sistema. Até mais!")
      break
    else:
      print("Opção inválida. Tente novamente.")

if __name__ == "__main__":
  main()