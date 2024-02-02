
import socket
import time
import struct

def tcp_server_socket():
    HOST = ""  # Set to the IP address of the server eth0 if you do not use docker compose 
    PORT = 8002  # Port to listen on (non-privileged ports are > 1023)

    print("TCP Server Started")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        conn, addr = s.accept()
        print("TCP Server Connected by", addr)
        with conn:
            #print(f"Connected by {addr}")
            while True:
                try:
                    data = conn.recv(1400)
                    if not data :
                        break
                except ConnectionResetError:
                    break

    conn.close()   
    return           

  
tcp_server_socket()       
  
#for i in range(30):
#    tcp_server_socket()
#    time.sleep(1)

