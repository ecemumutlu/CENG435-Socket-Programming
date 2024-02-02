import socket
import struct
import zlib
import hashlib
import time

def verify_checksum(data, received_checksum):
    calculated_checksum = zlib.crc32(data)
    return calculated_checksum == received_checksum



def receive_files(bind_address, buffer_size=2000):
    server_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
    server_socket.bind(bind_address)

    files_data = {}
    received_segments = {}
    expected_seq_nums = {}
    
    print("UDP server up and listening")

    while True:
        #print("Waiting for a segment")
        segment, client_address = server_socket.recvfrom(buffer_size + 12)
        #print("Received a segment")
        
        file_id, seq_num = struct.unpack('ii', segment[:8])
        data = segment[8:-4]  # Exclude the checksum part
        received_checksum = struct.unpack('I', segment[-4:])[0]
        #print(f"File ID: {file_id}, Segment Number: {seq_num}")
        
        # ----------------- CLOSE CONNECTION ----------------- #
        if file_id == -1 and seq_num == -1:
            #print("Received a FIN packet")
            
            # Write received file data to a file
            for file_id, data in files_data.items():
                with open(f'./received/received_file_{file_id}', 'wb') as file:
                    file.write(data)
                
            break
        
        ##########################################################
        
        if not verify_checksum(data, received_checksum):
            #print(f"Corrupted packet detected: File ID {file_id}, Segment Number {seq_num}")
            continue

        if file_id not in files_data:
            files_data[file_id] = bytearray()
            received_segments[file_id] = {}
            expected_seq_nums[file_id] = 0
            
        ### ------------------------NORMAL ------------------------------###
        if seq_num == expected_seq_nums[file_id]:
            files_data[file_id].extend(data)
            expected_seq_nums[file_id] += 1

            # Send ACK
            server_socket.sendto(struct.pack('II', file_id, seq_num), client_address)
            #print(f"Sent an ACK {file_id}.{seq_num}" )

            # ---------------------------Check buffered segments---------------------------#
            # when expected comes, extend the file for sequential increasing ones in the buffer
            tmp_seq_num = seq_num + 1 # expected next in buffered
            to_be_deleted = []
            for buffered_seq_num in received_segments[file_id].keys():
                if tmp_seq_num == buffered_seq_num:
                    #print(f"Send buffered to upper layer {file_id}.{buffered_seq_num}")
                    to_be_deleted.append(buffered_seq_num)
                    files_data[file_id].extend(received_segments[file_id][buffered_seq_num])
                    expected_seq_nums[file_id] += 1
                    tmp_seq_num += 1
                else:
                    break
                
            ## DELETE THE ONES AFTER THE REAL FILE IS EXTENDED
            for buffered_seq_num in to_be_deleted:
                if buffered_seq_num < tmp_seq_num:
                    del received_segments[file_id][buffered_seq_num]
                    
            
        ### ------------------------BUFFERING ------------------------------###    
        # send ACK for buffered segment, dont send again when previous expected is received
        # buffer the data until the expected comes.
        elif seq_num > expected_seq_nums[file_id]:
            if seq_num in received_segments[file_id].keys(): ## this file has received and buffered before but the ack was lost
                #print(f"Sent an ACK for lost buffered {file_id}.{seq_num}" )
                server_socket.sendto(struct.pack('II', file_id, seq_num ), client_address)
            else:
                received_segments[file_id][seq_num] = data
                #print(f"Buffered a segment {file_id}.{seq_num}")
                server_socket.sendto(struct.pack('II', file_id, expected_seq_nums[file_id] ), client_address)
                #print(f"Sent an ACK for buffered {file_id}.{seq_num}")
         
        ### -------------- LOST ACK - DUPLICATE FILE RECEIVED --------------###   
        elif seq_num < expected_seq_nums[file_id]:
            server_socket.sendto(struct.pack('II', file_id, seq_num ), client_address)
            #print(f"Sent an ACK for lost ACK {file_id}.{seq_num}")

    
    server_socket.close()
    return

# Example usage
#receive_files(('', 8020))

for i in range(30):
    receive_files(('', 8080))
    time.sleep(1)

