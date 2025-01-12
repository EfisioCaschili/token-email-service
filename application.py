from flask import Flask, request, jsonify
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import os
import datetime
from pathlib import Path
import sqlite3
import mysql.connector
import secrets
import hashlib
try:
    from dotenv import dotenv_values, load_dotenv
except:
    from dotenv import main 


path=str(Path.cwd()) + '/'
try:
    env=dotenv_values(path+'env.env')
    EMAIL_ADDRESS=env.get('EMAIL_ADDRESS')
    USER_DB=env.get('USER_DB')
    HOST=env.get('HOST')
    DB_PASSWORD=env.get('DB_PASSWORD')
    DATABASE=env.get('DATABASE')
    PORT=env.get('PORT')
    TOKEN_TABLE=env.get('TOKEN_TABLE')
except: 
    env=main.load_dotenv(path+'env.env')
    EMAIL_ADDRESS=os.getenv('EMAIL_ADDRESS')
    USER_DB=os.getenv('USER_DB')
    HOST=os.getenv('HOST')
    DB_PASSWORD=os.getenv('DB_PASSWORD')
    DATABASE=os.getenv('DATABASE')
    PORT=os.getenv('PORT')
    TOKEN_TABLE=os.getenv('TOKEN_TABLE')

app = Flask(__name__)

config = {
  'user': USER_DB,
  'password': DB_PASSWORD,
  'host': HOST,
  'database': DATABASE,
  'port':PORT
}


class Query():
    
    def dbConnection(self, config):
        try:
            conn = mysql.connector.connect(**config)
            print("Connected to " + config['database']+" with host "+config['host'])
            return conn
        except mysql.connector.Error as err:
            print(f"Connection Error: {err}")
            return False
        
    def check_token(self, attribute):
        try:
            conn = self.dbConnection(config)
            if not conn:
                print("Database connection failed")
                return False

            # Usa un blocco "with" per gestire il cursore
            with conn.cursor() as cursor:
                query = """
                    SELECT token, created_at, counter, user_token.id
                    FROM user_token
                    INNER JOIN email ON email_id = email.id
                    WHERE email.mail_address = %s
                """
                cursor.execute(query, (attribute,))
                result = cursor.fetchall()

            conn.close()
            print("Connection to DB closed")
            return result
        except Exception as e:
            print(f"Error occurred: {e}")
            return False
        
    def get_customer(self, name, surname):
        try:
            conn = self.dbConnection(config)
            if not conn:
                print("Database connection failed")
                return False

            # Usa un blocco "with" per gestire il cursore
            with conn.cursor() as cursor:
                query = """
                    SELECT id, gender
                    FROM customer
                    WHERE first_name = %s AND last_name = %s
                """
                cursor.execute(query, (name,surname))
                result = cursor.fetchone()

            conn.close()
            print("Connection to DB closed")
            if not result:
                return False
            return result
        except Exception as e:
            print(f"Error occurred: {e}")
            return False
    
    def get_email_parameters(self,sender_email):
        try:
            conn = self.dbConnection(config)
            if not conn:
                print("Database connection failed.")
                return False
            
            with conn.cursor() as cursor:
                # Ottenere il valore corrente del contatore
                query = "SELECT smtp_server,smtp_port,id FROM email WHERE mail_address = %s;"
                cursor.execute(query, (sender_email,))
                result = cursor.fetchall()
                if not result:
                    print(f"No record found with e-mail: {sender_email}")
                    return False
            print("E-mail parameters extracted successfully.")
            return result

        except Exception as e:
            print(f"An error occurred: {e}")
            return False
        finally:
            if conn:
                conn.close()
                print("Database connection closed.")

    def update_counter(self, user_id):
        try:
            conn = self.dbConnection(config)
            if not conn:
                print("Database connection failed.")
                return False
            
            with conn.cursor() as cursor:
                # Ottenere il valore corrente del contatore
                query = "SELECT counter FROM user_token WHERE id = %s;"
                cursor.execute(query, (user_id,))
                result = cursor.fetchone()

                if not result:
                    print(f"No record found with id: {user_id}")
                    return False
                counter = result[0] + 1
                update_query = "UPDATE user_token SET counter = %s WHERE id = %s;"
                cursor.execute(update_query, (counter, user_id))

            conn.commit()
            print("Counter updated successfully.")
            return counter

        except Exception as e:
            print(f"An error occurred: {e}")
            return False
        finally:
            if conn:
                conn.close()
                print("Database connection closed.")

    
    def create_new_row(self, data: dict):
        try:
            conn = self.dbConnection(config)
            if not conn:
                print("Database connection failed.")
                return False

            table = data.get('table')
            if not table:
                print("Table name not provided.")
                return False
            print(table)
            # Rimuovi 'table' dai dati e prepara i campi e i valori
            fields = [key for key in data.keys() if key != 'table']
            values = [data[key] for key in fields]
            print(fields)
            # Costruzione della query con placeholder
            placeholders = ', '.join(['%s'] * len(fields))
            field_names = ', '.join(fields)
            query = f"INSERT INTO {table} ({field_names}) VALUES ({placeholders})"

            # Esecuzione della query
            with conn.cursor() as cursor:
                cursor.execute(query, values)
                conn.commit()

            print("Row inserted successfully.")
            return True
        except Exception as e:
            print(f"Error occurred: {e}")
            return False
        finally:
            if conn:
                conn.close()
                print("Database connection closed.")

@app.route('/add-new-customer', methods=['POST'])
def add_new_customer():
    try:
        data = request.get_json()
        
        customer_id = Query().get_customer(data.get('name'),data.get('surname'))
        print(customer_id)
        if customer_id:
            return jsonify({'status': 'error', 'message': 'User already present'}), 400

        Query().create_new_row({'table':'customer',
                                'last_name':data.get('surname'),
                                'first_name':data.get('name'),
                                'gender':data.get('gender')
                                })
        
        customer_id = Query().get_customer(data.get('name'),data.get('surname'))[0]
        if not customer_id:
            return jsonify({'status': 'error', 'message': 'Error adding customer'}), 400

        Query().create_new_row({'table':'email',
                                'mail_address':data.get('mail_address'),
                                'pssword': data.get('password'),
                                'smtp_server':data.get('smtp_server'),
                                'customer_id':customer_id,
                                'smtp_port':587
                                })
        #geneeration of token
        token = secrets.token_hex(16)
        user_id=Query().get_email_parameters(data.get('mail_address'))[0][2]
        Query().create_new_row({'table':'user_token','email_id':user_id,'token':token})
        return jsonify({'status': 'success', 'message': 'User added in the database'}), 200

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500 

@app.route('/generate-token', methods=['POST'])
def generate_token(): 
    try:
        data = request.get_json()
        sender_email = data.get('sender_email')
        
        if not sender_email:
            return jsonify({'status': 'error', 'message': 'Sender email not specified'}), 400

        if not Query().get_email_parameters(sender_email):
            return jsonify({'status': 'error', 'message': 'Sender email not present in the database'}), 400
        #Token check
        result=Query().check_token(sender_email)
        print(result)
        if result:
            for x in result:
                if x[1]== datetime.date.today() and x[2]<10:
                    return jsonify({'status': 'success', 'message': 'Token recovered and not expired yet', 'token': x}), 200

        #New Token Saved
        # Token generation
        token = secrets.token_hex(16)
        user_id=Query().get_email_parameters(sender_email)[0][2]
        Query().create_new_row({'table':'user_token','email_id':user_id,'token':token})
        return jsonify({'status': 'success', 'message': 'Token generated successfully', 'token': token}), 201

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500      

@app.route("/")
def homepage():
    return str("Home Page")


@app.route('/send-email', methods=['POST'])
def send_email():
    try:
        token = request.headers.get('Authorization')
        if not token or not token.startswith("Bearer "):
            return jsonify({'status': 'error', 'message': 'Authentication failed. Missing or invalid token.'}), 401
        token = token.split("Bearer ")[1]
        

        data = request.get_json()
        sender_email = data.get('sender_email')
        result=Query().check_token(sender_email)
        if not result:
            return jsonify({'status': 'error', 'message': 'Authentication failed. No Token present for this account.'}), 401
        token_validity=False
        for x in result:
            if x[1] == datetime.date.today() and x[2] < 50:
                token_validity=True
                id=x[3]
                if token != x[0]:
                    return jsonify({'status': 'error', 'message': 'Authentication failed. Wrong Token used'}), 401
                break
        if not token_validity:
            return jsonify({'status': 'error', 'message': 'Authentication failed. Token expired.'}), 401
         
        parameters=Query().get_email_parameters(sender_email)
        EMAIL_PASSWORD=data.get('password')
        SMTP_SERVER=parameters[0][0]
        SMTP_PORT=parameters[0][1]
        recipient = data['recipient']
        subject = data['subject']
        content = data['content']
        print('Parameters read')

        msg = MIMEText(content)
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = recipient

        print('Msg set up completed')
        # Invia l'email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server: 
            server.starttls()
            print('Access Server completed')
            try:
                server.login(sender_email, EMAIL_PASSWORD)
            except smtplib.SMTPAuthenticationError as e:
                print(f'Login Error: {e.smtp_error.decode()}')
                return jsonify({'status': 'error', 'message': 'Authentication failed. Check email and password.'}), 401
            server.sendmail(sender_email, recipient, msg.as_string())

        # Risposta di successo
        Query().update_counter(id)
        return jsonify({'status': 'success', 'message': 'Email sent successfully!'}), 200

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
