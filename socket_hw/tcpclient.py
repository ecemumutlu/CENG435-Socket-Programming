# echo-client.py
import socket
import time
import time
import pickle as pkl

#HOST = socket.gethostbyname("server")  # Use this if you are using docker compose
# if you do not use docker compose, instead of resolving name
# set host to the ip address directly

def tcp_client_socket():
    HOST = "172.17.0.2"
    PORT = 8002  # socket server port number

    server_address = (HOST, PORT)
    client_socket = socket.socket()  # instantiate
    client_socket.connect((HOST, PORT))  # connect to the server

    start_time = time.time()
    obj_count = 0
    while obj_count != 10:
        
        # ------------------ 1 small object ------------------
        with open(f'../objects/small-{obj_count}.obj', 'rb') as file:
            while True:
                data = file.read(1400)
                if not data:
                    break
                client_socket.send(data)


        # ------------------ 1 large object ------------------
        with open(f'../objects/large-{obj_count}.obj', 'rb') as file:
            while True:
                data = file.read(1400)
                if not data:
                    break
                client_socket.send(data)

        obj_count += 1
    client_socket.shutdown(socket.SHUT_RDWR)
    client_socket.close()  # close the connection
    total_time = time.time() - start_time
    print("time taken to send 10 small 10 big object: ", total_time  )
    return total_time



tcp_client_socket()

#def run_experiment(num_runs=30):
#    run_times = []
#
#    # Running the experiment 'num_runs' times and recording the time taken for each run
#    for _ in range(num_runs):
#        print(f"Running experiment {_ + 1}")
#        time_taken = tcp_client_socket()
#        run_times.append(time_taken)
#        time.sleep(5)
#
#    with open('./results/tcp_loss_15percent.pkl', 'wb') as file:
#        pkl.dump(run_times, file)
#
#    print(run_times)
#    return run_times
#
#run_experiment()

