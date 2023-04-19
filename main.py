from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import psycopg2
from hubspot import HubSpot
from pyclickup import ClickUp
from hubspot.crm.contacts import ApiException, SimplePublicObjectInput, PublicObjectSearchRequest
from datetime import datetime
import requests
import json
from configparser import ConfigParser

parser = ConfigParser()
parser.read("config.ini")

list_id = parser['clickup']['listId']
url = parser['clickup']['endpoint'] + list_id + "/task"
token = parser['clickup']['token']

headers = {
  "Content-Type": parser['clickup']['contenType'],
  "Authorization": token,
}

access_token = parser['hubspot']['accesToken']


class ContactCreate(BaseModel):
    email: str
    firstname: str
    lastname: str
    phone: str
    website: str

conn = psycopg2.connect(
    host=parser['postgresql']['host'],
    database=parser['postgresql']['database'],
    user=parser['postgresql']['user'],
    password=parser['postgresql']['password'],
    port=parser['postgresql']['port'],
)

#Inicialización de Api
app = FastAPI()


def log_api_call(endpoint):
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM api_calls")
    logId = cursor.fetchall()[-1][-1]
    cursor.execute(f"INSERT INTO api_calls VALUES ({logId}, '{endpoint['date']}', '{endpoint['endpoint']}', '{json.dumps(endpoint['values'])}', '{endpoint['result']}')")
    conn.commit()
    cursor.close()

@app.post("/create-contact/")
async def create_contact(contact: ContactCreate):
    # crear contacto en HubSpot
    hubspot = HubSpot(access_token=access_token)
    
    try:
        properties = {
                "email" :  contact.email,
                "firstname" : contact.firstname,
                "lastname" : contact.lastname,
                "phone" :  contact.phone,
                "website" : contact.website,
                "estado_clickup" : "pending",
            }
        simple_public_object_input = SimplePublicObjectInput(properties=properties)

        apiResponse = hubspot.crm.contacts.basic_api.create(
            simple_public_object_input=simple_public_object_input
        )
        loggin = {
            "date" : datetime.now(),
            "endpoint" : 'sync_contact_with_clickup/',
            "values" : {
                'method' : 'POST',
                'email' :  contact.email,
                'firstname' : contact.firstname,
                'lastname' : contact.lastname,
                'phone' :  contact.phone,
                'website' : contact.website,
            },
            "result" : 'success'
        }
        log_api_call(loggin)
        return apiResponse.to_dict()
    except ApiException as e:
        loggin = {
            "date" : datetime.now(),
            "endpoint" : 'sync_contact_with_clickup/',
            "values" : {
                'method' : 'POST',
                'email' :  contact.email,
                'firstname' : contact.firstname,
                'lastname' : contact.lastname,
                'phone' :  contact.phone,
                'website' : contact.website,
            },
            "result" : 'failed'
        }
        log_api_call(loggin)
        return loggin

@app.get("/sync_contact_with_clickup/")
def sync_contact_with_clickup():
    # validar si el contacto ya ha sido sincronizado con ClickUp
    hubspot = HubSpot(access_token=access_token)
    try:

        stateClickup = "pending"
        public_object_search_request = PublicObjectSearchRequest(
            filter_groups=[
                {
                    "filters": [
                        {
                            "value": stateClickup,
                            "propertyName": "estado_clickup",
                            "operator": "EQ"
                        }
                    ]
                }
            ]
        )
        api_response = hubspot.crm.contacts.search_api.do_search(public_object_search_request=public_object_search_request).results
    # sincronizar contacto con ClickUp        
        for data in api_response:
            contact = data.properties
            payload = {
                "name":f"{contact['firstname']} {contact['lastname']} {contact['email']}",
            }
            response = requests.post(url, json=payload, headers=headers)
            # actualizar estado_clickup del contacto en HubSpot
            properties = {
                "estado_clickup": "added",
            }
            simple_public_object_input = SimplePublicObjectInput(properties=properties)
            response = hubspot.crm.contacts.basic_api.update(
                contact_id=data.id,
                simple_public_object_input=simple_public_object_input
            )

        # registrar llamada a la API en la base de datos
        loggin = {
            "date" : datetime.now(),
            "endpoint" : 'sync_contact_with_clickup/',
            "values" : {
                'method' : 'GET'
            },
            "result" : 'success'
        }
        log_api_call(loggin)
        
        return {"message":"Contacts added"}
    except ApiException as e:
        loggin = {
            "date" : datetime.now(),
            "endpoint" : 'sync_contact_with_clickup/',
            "values" : {
                'method' : 'GET',
            },
            "result" : 'failed'
        }
        log_api_call(loggin)
        return {"message" : "Ooops something went wrong"}


@app.get("/api-calls/")
async def get_api_calls():
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM api_calls")
    api_calls = cursor.fetchall()
    print(len(api_calls))
    cursor.close()

    # devolver registros de llamadas a la API
    return api_calls

