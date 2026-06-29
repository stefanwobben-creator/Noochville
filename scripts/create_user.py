"""Zet of reset een wachtwoord voor een persoon in data/people.json.

people.json is de enige bron van waarheid; er is geen aparte users.json meer.
De persoon moet al bestaan (toevoegen kan via de cockpit, Members-tab).
"""
import getpass, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from nooch_village.auth import hash_password
from nooch_village.people import PeopleStore

PEOPLE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "people.json")


def main():
    store = PeopleStore(PEOPLE_PATH)
    email = input("E-mailadres: ").strip()
    person = store.by_email(email)
    if person is None:
        print(f"Geen persoon gevonden met e-mailadres '{email}'.")
        print("Voeg de persoon eerst toe via de cockpit (Members-tab → Persoon toevoegen).")
        sys.exit(1)
    print(f"Gevonden: {person.name} ({person.email})")
    password  = getpass.getpass("Nieuw wachtwoord: ")
    password2 = getpass.getpass("Wachtwoord nogmaals: ")
    if password != password2:
        print("Wachtwoorden komen niet overeen.")
        sys.exit(1)
    if len(password) < 8:
        print("Wachtwoord moet minimaal 8 tekens zijn.")
        sys.exit(1)

    store.set_password(person.id, hash_password(password))
    print(f"Wachtwoord voor {person.name} opgeslagen in {PEOPLE_PATH}")


if __name__ == "__main__":
    main()
