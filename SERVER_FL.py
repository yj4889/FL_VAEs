
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sn
import torch
import socketserver
import threading
import copy
from utils.options import args_parser
from data.preprocess import data_preprocessing, load_train_data, load_tr_te_data
from model.Nets import VAE
from model.Update import *
from time import sleep

args = args_parser()
args.device = torch.device('cuda:{}'.format(args.gpu) if torch.cuda.is_available() and args.gpu != -1 else 'cpu')

HOST = ''
PORT = 9009
lock = threading.Lock() # syncronized 동기화 진행하는 스레드 생성


FL_Part = {}
neg_list = []
kl_list = []

class UserManager: # 사용자관리 및 채팅 메세지 전송을 담당하는 클래스
                   # ① 채팅 서버로 입장한 사용자의 등록
                   # ② 채팅을 종료하는 사용자의 퇴장 관리
                   # ③ 사용자가 입장하고 퇴장하는 관리
                   # ④ 사용자가 입력한 메세지를 채팅 서버에 접속한 모두에게 전송
 
    def __init__(self):
        self.users = {} # 사용자의 등록 정보를 담을 사전 {사용자 이름:(소켓,주소),...}
 
    def addUser(self, username, conn, addr): # 사용자 ID를 self.users에 추가하는 함수
        if username in self.users: # 이미 등록된 사용자라면
            conn.send('이미 등록된 사용자입니다.\n'.encode())
            return None
 
        # 새로운 사용자를 등록함
        lock.acquire() # 스레드 동기화를 막기위한 락
        self.users[username] = (conn, addr)
    
        FL_Part[int(username)] = [0, (conn, addr)]
        
        lock.release() # 업데이트 후 락 해제
 
        #self.sendMessageToAll('[%s]님이 입장했습니다.' %username)
        print('+++ 대화 참여자 수 [%d]' %len(self.users))
         
        return username
 
    def removeUser(self, username): #사용자를 제거하는 함수
        if username not in self.users:
            return
 
        lock.acquire()
        del self.users[username]
        lock.release()
 
        self.sendMessageToAll('[%s]님이 퇴장했습니다.' %username)
        print('___the number of Rasberry Pi parti [%d]' %len(self.users))
 
    def messageHandler(self, username, msg, neg_kl): # 전송한 msg를 처리하는 부분
        if msg[0] != '/': # 보낸 메세지의 첫문자가 '/'가 아니면
            
            if neg_kl == 0 :
                #lock.acquire()
                np_neg = np.frombuffer(msg, dtype = np.float32)
                neg_list.append(np_neg[0])
                
                #lock.release()
            
                
            else :
                #lock.acquire()
                np_kl = np.frombuffer(msg, dtype = np.float32)
                kl_list.append(np_kl[0])
                #lock.release()
            #self.sendMessageToAll('[%s] %s' %(username, msg))
            
            return
        else:
            msg = msg.decode()
            if msg.strip() == '/quit': # 보낸 메세지가 'quit'이면
                self.removeUser(username)
                return -1
 
    def sendMessageToAll(self, msg):
        for conn, addr in self.users.values():
            conn.send(msg.encode())
           
 
class MyTcpHandler(socketserver.BaseRequestHandler):
    userman = UserManager()
    
    def handle(self): # 클라이언트가 접속시 클라이언트 주소 출력
        
        print('[%s] 연결됨' %self.client_address[0])
 
        try:
            username = self.registerUsername()
          
            #self.sendModel(username = username)
            print("user::", username)

            msg = self.request.recv(1024)
          
            neg_kl = 0  # =0 이면 neg, =1 이면 KL
            while True:
                
                if self.userman.messageHandler(username, msg, neg_kl) == -1:
                    self.request.close()
                    break

                if neg_kl == 0 : neg_kl = 1
                else : neg_kl = 0
                        
                msg = self.request.recv(1024)
                 
        except Exception as e:
            print(e)
 
        print('[%s] 접속종료' %self.client_address[0])
        self.userman.removeUser(username)
 
    def registerUsername(self):
        while True:
            self.request.send('로그인ID:'.encode())
            username = self.request.recv(1024)
            username = username.decode().strip()
            if self.userman.addUser(username, self.request, self.client_address):
                return username
    '''
    def sendModel(self, username):
        
        conn = FL_Part[1][1][0]
        conn.send(eof)

        with open(args.model_dir, 'rb') as f:
            
            try:
                data = f.read(1024) # 파일을 1024바이트 읽음
                while data: # 파일이 빈 문자열일때까지 반복
                    conn.send(data)
                    data = f.read(1024)  
                
            except Exception as e:
                print(e)

        print("1")
        eof = b'/end'
        conn.send(eof)
    
        print("전송완료")
    '''
class ChatingServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass


def st_sock():
    try:
        server = ChatingServer((HOST, PORT), MyTcpHandler)
        server.serve_forever()
    except KeyboardInterrupt:
        print('--- 채팅 서버를 종료합니다.')
        server.shutdown()
        server.server_close()


def sendModel():
    sleep(2)
    print("전송시작")
    with open(args.model_dir, 'rb') as f:
        try:
            data = f.read(1024) # 파일을 1024바이트 읽음
    
            while data: # 파일이 빈 문자열일때까지 반복
                for part, (conn, addr) in FL_Part.values():
                    if part == 1 :
                        conn.send(data)
                data = f.read(1024)
           
        except Exception as e:
            print(e)
    
    
    eof = b'/end'
    for part, (conn, addr) in FL_Part.values():
        if part == 1 :
            conn.send(eof)
    
    print("전송완료")
    

if __name__ == '__main__':
  
    
    
    print(torch.cuda.is_available())

    if args.device.type == 'cuda':
        print(torch.cuda.get_device_name(0))
        print('Memory Usage:')
        print('Allocated:', round(torch.cuda.memory_allocated(0)/1024**3,1), 'GB')
        print('Cached:   ', round(torch.cuda.memory_cached(0)/1024**3,1), 'GB')
   
    
    #isNotProcessed == 1 for preprocessing
    if args.preprocess == 1 :
        #Data Preprocessing
        data_preprocessing(args.data_dir)

    pro_dir = os.path.join(args.data_dir, 'pro_sg')
  
    #getting user's unique id
    unique_sid = list()
    with open(os.path.join(pro_dir, 'unique_sid.txt'), 'r') as f:
        for line in f:
            unique_sid.append(line.strip()) #line.strip() 양쪽 공백과 \n을 삭제해준다.

    n_items = len(unique_sid)
       
    train_data = load_train_data(os.path.join(pro_dir, 'train.csv'), n_items)
    
    ###########################################################################################################################처음에만 하기
    #10 user's data distribute
    user_dir = os.path.join(args.data_dir, 'pro_sg/user_data')
    if not os.path.exists(user_dir):
        os.makedirs(user_dir)
    for i in args.user_IDs:
        #store user's data
        pd.DataFrame(train_data[i].indices, columns=['sid']).to_csv(os.path.join(user_dir, 'user{}.csv'.format(i)), index=False)

         #pd.DataFrame(data={'uid': uid, 'sid': sid}, columns=['uid', 'sid'])

    vad_data_tr, vad_data_te = load_tr_te_data(os.path.join(pro_dir, 'validation_tr.csv'), os.path.join(pro_dir, 'validation_te.csv'), n_items)
    
    #number of data size
    N = train_data.shape[0]
    N_vad = vad_data_tr.shape[0]

    idxlist = range(N)

    # training batch size
    batches_per_epoch = int(np.ceil(float(N) / args.batch_size)) #np.ceil() 은 요소들을 올림 ######################################################################

    N_vad = vad_data_tr.shape[0]

    idxlist_vad = range(N_vad)
    
    #Model size
    p_dims = [200, 600, n_items]

    #build model
    model = VAE(p_dims).to(args.device)
    print(model)
    
    #training
    ndcgs_list = []
    r20_list = []
    r50_list = []
    loss_list = []

    best_ndcg = -np.inf
    #for annealing
    update_count = 0.0
    
    
    #SOCKET
    print('___FL Server Start')
    
    th_socket = threading.Thread(target = st_sock, daemon= True)
    th_socket.start()
    

    while True:
        if len(FL_Part) >= args.n_RasPart :
            break
    print('___FL Start')

    

    for epoch in range(args.n_epochs) :
        #FL participants
        idxs_users = np.random.choice(N, args.n_participants, replace=False)
        idxs_users[0] = 1
        idxs_users[1] = 2
        idxs_users[2] = 3
        
        idxs_users[3] = 4
        idxs_users[4] = 5
     
        idxs_users[5] = 6
        idxs_users[6] = 7
        
        #idxs_users[7] = 8
        #idxs_users[8] = 9
        #idxs_users[9] = 10 
        
        #model store
        torch.save(model.state_dict(), args.model_dir)
        n_RasInPart = 0  #the number of Rasberry_participants in participants
        for i in FL_Part.keys():     
            if i in idxs_users:
                #delete data in Users(Rasberry pi)
                idxs_users = np.delete(idxs_users, np.where(idxs_users==i))
                FL_Part[i][0] = 1
                n_RasInPart += 1

        
        sendModel()
        
 
        #data of FL participants
        data = torch.FloatTensor(train_data[idxs_users].toarray()).to(args.device)

        idx_client = 0
            
        total_loss = 0 

        local_up = Local_Update(args = args)

        #for getting Rasberrypi's loss
        while True:
            #print(n_RasInPart)
            #print(len(neg_list))
            if n_RasInPart == len(neg_list) and n_RasInPart == len(kl_list):
                break
        print("|__epochs", epoch)
        print("neg_list", neg_list)
        print("kl_list", kl_list)
        w, loss, update_count = local_up.train(net = model, train_data = data, update_count = update_count, neg_list = neg_list, kl_list = kl_list)
        
        

        model.load_state_dict(w)

        neg_list = []
        kl_list = []
   
        for i in FL_Part.keys():
            FL_Part[i][0] = 0
   
        if epoch % args.check_point == 0:
            # compute validation NDCG            
            ndcg_,r20, r50 = evaluate(args, model, vad_data_tr, vad_data_te, update_count)
        
            ndcgs_list.append(ndcg_)
            r20_list.append(r20)
            r50_list.append(r50)
            loss_list.append(loss.item())

            print("||epochs::",epoch,"\t||recall20::",r20,"\t||recall50::",r50,"\t||ndcg::", ndcg_,"\t||loss::", loss.item(),"||")

            # update the best model (if necessary)
            if ndcg_ > best_ndcg:
                best_ndcg = ndcg_
    
    plt.figure(figsize=(12, 3))
    plt.plot(ndcgs_list)
    plt.plot(r20_list)
    plt.plot(r50_list)
    plt.ylabel("Validation NDCG@100")
    plt.xlabel("Epochs")        
    plt.savefig('./log/performance.png')

    
    plt.figure(figsize=(12, 3))
    plt.plot(loss_list)
    plt.ylabel("Loss")
    plt.xlabel("Epochs")        
    plt.savefig('./log/loss.png')        


        
   


    


