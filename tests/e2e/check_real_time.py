import sys
import socket
import struct
import time

def get_ntp_time():
    NTP_SERVER = "pool.ntp.org"
    TIME1970 = 2208988800
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    data = b'\x1b' + 47 * b'\0'
    try:
        client.settimeout(5)
        client.sendto(data, (NTP_SERVER, 123))
        data, address = client.recvfrom(1024)
        if data:
            t = struct.unpack('!12I', data)[10]
            t -= TIME1970
            return t
    except Exception as e:
        print(f"NTP Error: {e}")
        return None

def get_http_time():
    import http.client
    try:
        conn = http.client.HTTPConnection("google.com")
        conn.request("HEAD", "/")
        res = conn.getresponse()
        date_str = res.getheader('Date')
        print(f"HTTP Date: {date_str}")
        import email.utils
        parsed = email.utils.parsedate_tz(date_str)
        timestamp = email.utils.mktime_tz(parsed)
        return timestamp
    except Exception as e:
        print(f"HTTP Error: {e}")
        return None

if __name__ == "__main__":
    real_time = get_ntp_time()
    if not real_time:
        real_time = get_http_time()
    
    if real_time:
        print(f"Real Time: {real_time}")
        print(f"System Time: {time.time()}")
        print(f"Diff: {time.time() - real_time}")
    else:
        print("Could not get real time")
