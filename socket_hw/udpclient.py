import socket
import struct
import os
import time
import zlib  #used for checksum
import threading
import pickle as pkl


#on the client side, I used two threads one for sending and one for receiving.
# sending thread sends the segments in an interleaved manner. Each file has its own window size.
# receiving thread receives the acks and updates acked variable of the segment whose ack is received.
# for the case of packet loss, I used a timer for each segment. If the timer expires, the segment is resent.

server_address = ('172.17.0.2', 8080)

files = dict()
client_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
all_files_sent = 0
total_segment_count = 0
client_socket_closed: bool = False
client_socket_closed_lock = threading.Lock()
finished_time = 0


def calculate_checksum(data):
    return zlib.crc32(data)

class Segment:
    def __init__(self, file_id, file_seq_num, data):
        self.file_id = file_id
        self.file_seq_num = file_seq_num
        self.data = data
        self.sent = False
        self.acked = False
        self.sent_time = 0
        self.timeout: bool = False

        self.acked_lock = threading.Lock()
        self.sent_lock = threading.Lock()

    def __str__(self):
        return f"File ID: {self.file_id},  File Segment Number: {self.file_seq_num}"
    
    def startTimer(self):
        with self.sent_lock:
            self.sent = True
        self.sent_time = time.time()

        
    def acknowledgeSelf(self):
        with self.acked_lock:
            self.acked = True

        
class File:
    def __init__(self, file_id, segments, checksums):
        self.segments = segments # {seq_num: Segment, ...} pairs
        self.checksums = checksums # {seq_num: checksum, ...} pairs
        self.file_id = file_id # file_id of the file
        self.num_segments = len(self.segments.keys())
        self.window_size = (self.num_segments - 1) // 2
        self.send_base = 0 # seq_num of the oldest unACKed segment
        self.window_end = min(self.send_base + self.window_size , self.num_segments) # seq_num of the last segment in the window
        self.to_be_sent = list(range(self.send_base, self.window_end))# set of seq_nums to be sent
        self.finished = False
        
        self.finished_lock = threading.Lock()
        
    # this functions updates the window by checking the acked variable of the segment
    def updateToBeSent(self):
        for seg_num in self.to_be_sent:
            curr_segment : Segment = self.segments[seg_num]
            with curr_segment.acked_lock:
                if curr_segment.acked == True:
                    if seg_num == self.send_base:
                        self.send_base += 1
                    else:
                        break

        if self.send_base == self.num_segments:
            with self.finished_lock:
                self.finished = True
        self.window_end = min(self.send_base + self.window_size , self.num_segments)
        self.to_be_sent = list(range(self.send_base, self.window_end))
                    

    
        
        
def read_files(file_paths, segment_size=2000):
    global all_files_sent
    global total_segment_count
    global files
    
    # Prepare segments for each file
    for file_id, file_path in enumerate(file_paths):
        with open(file_path, 'rb') as file:
            file_size = os.path.getsize(file_path)
            # If file size is larger than a threshold, segment it
            if file_size > segment_size:
                num_segments = file_size // segment_size + (1 if file_size % segment_size else 0)

                curr_segments = dict()
                curr_checksums = dict()
                for i in range(num_segments):  
                    curr_segments[i] = Segment(file_id=file_id, file_seq_num=i, data=file.read(segment_size))
                    curr_checksums[i] = calculate_checksum(curr_segments[i].data)

                files[file_id] = File(file_id, curr_segments, curr_checksums)

            else:
                # If file is small, send it in one segment
                data = file.read()
                curr_segments = dict()
                curr_checksums = dict()
                curr_segments[0] = Segment(file_id, 0, data)
                curr_checksums[0] = calculate_checksum(curr_segments[0].data)
                total_segment_count += 1
                files[file_id] = File(file_id, curr_segments, curr_checksums)
            
            all_files_sent += 1
            
    return 

# This function is used for finding the segment to be sent in the current window
def find_next_to_be_sent(file):
    for seg_num in file.to_be_sent:
        segment: Segment = file.segments[seg_num]
        with segment.sent_lock:
            if segment.sent == False:
                return seg_num

        if segment.timeout == True:
            segment.sent_time = 0
            segment.timeout = False
            return seg_num
                
    
    return -1

def send_files():
    global all_files_sent
    global client_socket_closed
    global finished_time
    global files
    

    while True:
        total_finished_docs = 0
        for file_id, file in files.items():
            file.updateToBeSent() ##todo:: change this
            with file.finished_lock:
                if file.finished == True:
                    total_finished_docs += 1
                    continue
            seg_num = find_next_to_be_sent(file)
            if seg_num == -1:
                continue
                
            segment: Segment = file.segments[seg_num]
            
            data = segment.data
            packed_data = struct.pack('ii', file_id, seg_num) + data + struct.pack('I', file.checksums[seg_num])
            
            client_socket.sendto(packed_data, server_address)
            #print(f"Sending segment: File ID {file_id}, Segment Number {seg_num}")
            
            #segment.timeout.join()
            segment.startTimer()
        
        if total_finished_docs == all_files_sent:
            with client_socket_closed_lock:
                client_socket_closed = True
            break
            
        checkWindowTimeout()
        
        
    packed_data = struct.pack('ii', -1, -1)
    client_socket.sendto(packed_data, server_address)
    finished_time = time.time()     
    return 
            
        
def checkWindowTimeout():
    global files
    for file_id, file in files.items():
        for seg_num in file.to_be_sent:
            curr_segment = file.segments[seg_num]
            with curr_segment.sent_lock:
                if curr_segment.sent == False:
                    continue
            
            current_time = time.time()
            if current_time - curr_segment.sent_time > 0.1:

                curr_segment.timeout = True
                #print(f"Timeout: File ID {file_id}, Segment Number {seg_num}")
                

def receive_acks():
    global client_socket
    global files
    global client_socket_closed
    global client_socket_closed_lock
    
    while True:
        #try:
        try:
            client_socket.settimeout(2.0)
            ack_packet, _ = client_socket.recvfrom(8)
            client_socket.settimeout(None)
                
            ack_file_id, ack_seq_num = struct.unpack('II', ack_packet)
            #print(f"Received ACK: File ID {ack_file_id}, Segment Number {ack_seq_num}")

            file = files[ack_file_id]
            curr_segment = file.segments[ack_seq_num]

            curr_segment.acknowledgeSelf()
            

        except socket.timeout:
            with client_socket_closed_lock:
                if client_socket_closed == True:
                    break
                
    client_socket_closed = False
    client_socket.close() # for doing experiemnts, comment this
    return

def udp_client():
    global finished_time
    global files
    global client_socket
    global total_segment_count
    global client_socket_closed
    global files_names_list
    global all_files_sent
    
    files = dict()
    client_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
    all_files_sent = 0
    total_segment_count = 0
    client_socket_closed = False
    finished_time = 0
    files_names_list = list()
    
    for i in range(10):
        files_names_list.append(f'../objects/small-{i}.obj')
        files_names_list.append(f'../objects/large-{i}.obj')

    start_time = time.time()
    read_files(files_names_list)
    
    t1 = threading.Thread(target = send_files, args = ())
    t2 = threading.Thread(target = receive_acks, args = ())
    
    t1.start()
    t2.start()
    
    t1.join()
    t2.join()
    
    print(f"Total time: {finished_time - start_time}")
    return finished_time - start_time
    
# example usage
udp_client()

#def run_experiment(experiment_name, num_runs=30):
#    run_times = []
#
#    # Running the experiment 'num_runs' times and recording the time taken for each run
#    for i in range(num_runs):
#        print(f"Running experiment {i + 1}")
#       time_taken = udp_client()
#        run_times.append(time_taken)
#        time.sleep(5)
#
#    with open(f'./results/{experiment_name}.pkl', 'wb') as file:
#        pkl.dump(run_times, file)
#
#    print(run_times)
#    return run_times

#run_experiment("delay100ms_normaldist20")
