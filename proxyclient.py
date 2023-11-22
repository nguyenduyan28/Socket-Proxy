import socket
import threading
import configparser
import datetime
import time


HEADER = 4096
PORT = 8888
SERVER = "localhost"

with open('config.txt', 'r') as file:
    datalist = file.readlines()

with open("403.html", "r") as file:
    forbidden_html = file.read()


# Tách phần white_list từ nội dung config
white_list_start = datalist[0].find('whitelisting = ') + len('whitelisting = ')
white_list = datalist[0][white_list_start:].strip()



# Tách time từ config
time_start = datalist[1].find('time = ') + len('time = ')
times = datalist[1][time_start:].strip()
time_parts = times.split('-')
start_hour = int(time_parts[0])
end_hour = int(time_parts[1])
current_hour = datetime.datetime.now().hour

# Thời gian để xóa cache
time_cache_start = datalist[2].find('time_cache = ') + len('time_cache = ')
time_cache_str = datalist[2][time_cache_start:].strip()
time_cache = int(time_cache_str)
# Chia danh sách thành các trang web
allowed_websites = [website.strip() for website in white_list.split(',')]
print(allowed_websites)
image_cache = {}


server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((SERVER, PORT)) 
def get_web_server_info(request):
    # Tìm phần URL trong yêu cầu HTTP
    first_line = request.split('\n')[0]
    url = first_line.split(' ')[1]

    # Tách phần host từ URL
    try:
        host = url.split('/')[2]
    except IndexError:
        raise ValueError("Invalid HTTP request: Missing URL")

    # Tách địa chỉ và cổng từ phần host
    if ':' in host:
        address, port = host.split(':')
        port = int(port)
    else:
        address = host
        port = 80  # Nếu không có cổng được chỉ định, mặc định là cổng 80

    return address, port
def get_path(url):
    # Tách phần scheme và netloc
    scheme_end = url.find("://")
    if scheme_end == -1:
        return None
    netloc_start = scheme_end + 3
    netloc_end = url.find("/", netloc_start)
    if netloc_end == -1:
        return None

    # Tìm và trích xuất đường dẫn
    path_start = netloc_end
    path = url[path_start:]
    return path


def handle_client(client_socket):
    request = client_socket.recv(HEADER)
    request = request.decode("utf-8")
    print(request)
    if len(request) < 0:
        print("Error in request")
    else:
       # Biến đổi từ điển image_cache thành một chuỗi dạng văn bản
        method = request.split()[0]
        print(f"Received request with method: {method}")
        if method == "GET" or method == "POST" or method == "HEAD":
            # make a server socket to receive the request
            first_line = request.split('\n')[0]
            url = first_line.split(' ')[1]
            print("url is:", url)
            web_server_address, web_server_port = get_web_server_info(request)
            # Kiểm tra xem trang web có nằm trong danh sách được quyền truy cập không
            if web_server_address in allowed_websites and start_hour <= current_hour <= end_hour:
                web_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                web_server.connect((web_server_address, web_server_port))
                path = get_path(url)
                old_line = request.split('\n')[0]
                new_line = old_line.replace(url, path)
                request = request.replace(old_line, new_line)
                web_server.sendall(request.encode("utf-8"))
                if image_cache.get(url) is not None:
                    print("Loading cache:")
                    client_socket.sendall(image_cache[url])
                    client_socket.close()
                    return
                response = b""
                content_length = -1
                chunked_response = b""  # Tích luỹ chuỗi chunks
                content_type =""
                while True:
                    data = web_server.recv(HEADER)
                    if not data:
                        break
                    response += data
                    chunked_response += data  # Tích luỹ chuỗi chunks
                    if method == "HEAD":
                        if b"\r\n\r\n" in response:
                            break
                    if b"Transfer-Encoding: chunked" in response:
                        # Kiểm tra xem chuỗi chunks đã kết thúc chưa
                        if b"\r\n0\r\n\r\n" in chunked_response:
                            break
                    else:
                        # Xử lý khi không sử dụng chunked encoding
                        if content_length == -1:
                            content_index = response.find(b"Content-Length: ")
                            if content_index != -1:
                                end_of_content_index = response.find(b"\r\n", content_index)
                                if end_of_content_index != -1:
                                    content_length = int(response[content_index + len(b"Content-Length: "):end_of_content_index])
                        if content_length != -1 and len(response) >= content_length:
                            break
                    if content_type == "":
                        content_type_index = response.find(b"Content-Type: ")
                        if content_type_index != -1:
                            end_of_content_type_index = response.find(b"\r\n", content_type_index)
                            if end_of_content_type_index != -1:
                                content_type = response[content_type_index + len(b"Content-Type: "):end_of_content_type_index].decode("utf-8")
                if content_type.startswith("image/") and url not in image_cache:
                    image_cache[url] = response
                    cache_content = "\n".join([f"{url}:::{image_data}" for url, image_data in image_cache.items()])
                    with open("cache.txt", "w") as cache_file:
                        cache_file.write(cache_content)
                client_socket.sendall(response)
                # print("\n", "Len response data: ", len(response))
                web_server.close()
            else:
                response = "HTTP/1.1 403 Forbidden\r\nContent-Length: {}\r\n\r\n{}".format(len(forbidden_html), forbidden_html)
                print("Error 403: ")
                client_socket.sendall(response.encode("utf-8"))

        elif method == "PUT" or method == "DELETE" or method == "PATCH" or method == "OPTIONS":
            response = "HTTP/1.1 403 Forbidden\r\nContent-Length: {}\r\n\r\n{}".format(len(forbidden_html), forbidden_html)
            print("Error 403: ")
            client_socket.sendall(response.encode("utf-8"))
        client_socket.close()
# ...

def check_and_clear_cache():
    while True:
        time.sleep(time_cache)
        print(time_cache)  # Đợi 15 phút (900 giây)
        print("Clearing cache...")
        image_cache.clear()
        with open("cache.txt", "w") as cache_file:
            cache_file.write("")

def start_proxy():
    server.listen(5)
    print(f"[LISTENING] Proxy server is listening on {SERVER}:{PORT}")
    # Đọc nội dung tệp
    with open("cache.txt", "r") as cache_file:
        cache_content = cache_file.readlines()
        for line in cache_content:
            if ":::" in line:
                url = line.split(':::')[0]
                data = line.split(':::')[1]
                data = bytes(data, 'utf-8')
                image_cache[url] = data

# Tạo lại từ điển image_cache từ nội dung tệp
    while True:
        client_socket, client_addr = server.accept()
        print(f"[NEW CONNECTION] Client connected from {client_addr}")
        client_thread = threading.Thread(target=handle_client, args=(client_socket,))
        client_thread.start()

clear_cache_thread = threading.Thread(target=check_and_clear_cache)
clear_cache_thread.start()


start_proxy()
