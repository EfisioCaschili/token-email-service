from flask import Flask, request, jsonify
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import datetime
from pathlib import Path
import sqlite3
import mysql.connector
import secrets
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
            print("Connected to " + config['database'])
            return conn
        except mysql.connector.Error as err:
            print(f"Connection Error: {err}")
            return False
        
    def check_token(self,attribute):
        try:
            conn=self.dbConnection(config)
            cursor=conn.cursor()
            if cursor==False:
                return False
            query="SELECT token,created_at,counter,user_token.id FROM `user_token` INNER JOIN email on email_id=email.id \
                   WHERE email.mail_address='"+attribute+"';"
            #cursor.execute("SELECT token FROM "+table_name+" WHERE email = '"+attribute+"';")
            cursor.execute(query)
            result = cursor.fetchall()
            cursor.close()
            conn.close()
            print('Connection to DB closed')
            return result
        except Exception as creationError: 
            print(creationError)
            return False
    
    def get_email_parameters(self,sender_email):
        try:
            conn = self.dbConnection(config)
            if not conn:
                print("Database connection failed.")
                return False
            
            with conn.cursor() as cursor:
                # Ottenere il valore corrente del contatore
                query = "SELECT pssword,smtp_server,smtp_port FROM email WHERE mail_address = %s;"
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

    
    def create_new_row(self, data:dict):
        try:
            conn=self.dbConnection(config)
            cursor=conn.cursor()
            if cursor==False:
                return False
            attributes=list(data.keys())
            attributes.remove('table')
            query="INSERT INTO "+str(data['table']) + '('
            for x in attributes:
                query=query+x+','
            query=query[:-1]
            query=query+') VALUES ('
            for x in attributes:
                query=query+"'"+data[x]+"',"
            query=query[:-1]
            query=query+');'

            cursor.execute(query) 
            conn.commit()
            cursor.close()
            conn.close()
            print('Connection to DB closed')
            return True
        except Exception as creationError: 
            print(creationError)
            return False

@app.route('/generate-token', methods=['POST'])
def generate_token(): 
    try:
        data = request.get_json()
        sender_email = data.get('sender_email')

        if not sender_email:
            return jsonify({'status': 'error', 'message': 'Sender email missing'}), 400
        
        # Token generation
        token = secrets.token_hex(16)

        #Token check
        result=Query().check_token(sender_email,TOKEN_TABLE)

        if result:
            return jsonify({'status': 'success', 'message': 'Token recovered', 'token': result[0]}), 200

        #New Token Saved
        Query().create_new_row({'table':TOKEN_TABLE,'email':sender_email,'token':token})
        return jsonify({'status': 'success', 'message': 'Token generated successfully', 'token': token}), 201

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500      

@app.route("/")
def homepage():
    return str("Home Page")


@app.route('/send-email', methods=['POST'])
def send_email():
    try:
        data = request.get_json()
        sender_email = data.get('sender_email')
        result=Query().check_token(sender_email)
        if not result:
            return jsonify({'status': 'error', 'message': 'Authentication failed. No Token present for this account.'}), 401
        token_validity=False
        for x in result:
            if x[1] == datetime.date.today() and x[2] < 100:
                token_validity=True
                id=x[3]
                break
        if not token_validity:
            return jsonify({'status': 'error', 'message': 'Authentication failed. Token expired.'}), 401
        
        parameters=Query().get_email_parameters(sender_email)
        EMAIL_PASSWORD=parameters[0][0]
        SMTP_SERVER=parameters[0][1]
        SMTP_PORT=parameters[0][2]
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
            except smtplib.SMTPAuthenticationError:
                print('Login Error')
                return jsonify({'status': 'error', 'message': 'Authentication failed. Check email and password.'}), 401
            server.sendmail(sender_email, recipient, msg.as_string())

        # Risposta di successo
        Query().update_counter(id)
        return jsonify({'status': 'success', 'message': 'Email sent successfully!'}), 200

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500



app.run(debug=True)
