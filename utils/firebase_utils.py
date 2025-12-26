import json
import os

import firebase_admin
from firebase_admin import credentials, firestore

try:
    import streamlit as st
except Exception:
    st = None

def init_firestore():
    if not firebase_admin._apps:
        if st is not None:
            try:
                if "firebase" in st.secrets:
                    cred = credentials.Certificate(dict(st.secrets["firebase"]))
                else:
                    cred = _cred_from_env_or_file()
            except Exception:
                cred = _cred_from_env_or_file()
        else:
            cred = _cred_from_env_or_file()
        firebase_admin.initialize_app(cred)
    return firestore.client()


def _cred_from_env_or_file():
    service_account_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
    if service_account_json:
        cred_info = json.loads(service_account_json)
        return credentials.Certificate(cred_info)
    return credentials.Certificate("secrets/key.json")
