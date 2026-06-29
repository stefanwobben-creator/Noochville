"""Voeg een gebruiker toe aan data/users.json (of update een bestaande)."""
import getpass, json, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from nooch_village.auth import hash_password

USERS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "users.json")


def main():
    username = input("Gebruikersnaam: ").strip()
    if not username:
        print("Gebruikersnaam mag niet leeg zijn.")
        sys.exit(1)
    person_id   = input("person_id (bijv. dc5685eb2074, of Enter om leeg te laten): ").strip()
    display_name = input("Display naam (bijv. Stefan Wobben): ").strip()
    password    = getpass.getpass("Wachtwoord: ")
    password2   = getpass.getpass("Wachtwoord nogmaals: ")
    if password != password2:
        print("Wachtwoorden komen niet overeen.")
        sys.exit(1)
    if len(password) < 8:
        print("Wachtwoord moet minimaal 8 tekens zijn.")
        sys.exit(1)

    users = {}
    if os.path.exists(USERS_PATH):
        users = json.load(open(USERS_PATH, encoding="utf-8"))

    users[username] = {
        "password_hash": hash_password(password),
        "person_id":     person_id or None,
        "display_name":  display_name or username,
    }

    with open(USERS_PATH, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

    print(f"Gebruiker '{username}' opgeslagen in {USERS_PATH}")


if __name__ == "__main__":
    main()
