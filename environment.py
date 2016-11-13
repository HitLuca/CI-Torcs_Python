import os
import socket
import sys
import time
from xml.etree import ElementTree as etree

import utils
from algorithm import algorithm

data_size = 2 ** 17


class Environment:
    def __init__(self, host='localhost', port=3001, sid='SCR', track='forza', track_type='road', gui=True):
        self.gui = gui
        self.server = self.Server(track, track_type, gui)
        self.client = self.Client(self.server, host, port, sid)

    def step(self, actions):
        return self.client.step(actions)

    def restart_environment(self):
        self.server.restart()
        self.client.restart()

    def restart_race(self):
        if self.gui:
            self.client.send_restart_request()
            self.client.restart()
        else:
            self.restart_environment()

    def check_sensors(self, sensors):
        if abs(sensors['trackPos']) > 1:
            print("out of track!")
            self.restart_race()

    class Server:
        quickrace_xml_path = os.path.expanduser('~') + '/.torcs/config/raceman/quickrace.xml'

        def __init__(self, track, track_type, gui):
            self.track = track
            self.track_type = track_type
            self.gui = gui

            self.create_race_xml()
            self.init_server()

        def init_server(self):
            os.system('pkill torcs')
            time.sleep(0.1)
            if self.gui is True:
                if utils.cmd_exists('optirun'):
                    os.system('optirun torcs -nofuel -nodamage -nolaptime &')
                else:
                    os.system('torcs -nofuel -nodamage -nolaptime &')
                time.sleep(2)
                os.system('sh autostart.sh')
            else:
                os.system('torcs -nofuel nodamage -nolaptime -r ' + self.quickrace_xml_path + ' &')
            print('Server created!')
            time.sleep(0.1)

        def restart(self):
            print('Restarting server...')
            os.system('pkill torcs')
            time.sleep(0.5)
            self.init_server()

        def create_race_xml(self):
            root = etree.parse(self.quickrace_xml_path)
            track_name = root.find('section[@name="Tracks"]/section[@name="1"]/attstr[@name="name"]')
            track_name.set('val', self.track)
            track_type = root.find('section[@name="Tracks"]/section[@name="1"]/attstr[@name="category"]')
            track_type.set('val', self.track_type)
            root.write(self.quickrace_xml_path)

    class Client:
        def __init__(self, server, host, port, sid):
            self.server = server
            self.host = host
            self.port = port
            self.sid = sid

            self.socket = self.create_socket()
            self.connect_to_server()

        def restart(self):
            self.socket = self.create_socket()
            self.connect_to_server()

        def send_restart_request(self):
            actions = utils.get_empty_actions()
            actions['meta'] = True
            message = self.encode_actions(actions)
            self.send_message(message)

        def send_message(self, message):
            try:
                self.socket.sendto(message.encode(), (self.host, self.port))
            except socket.error as emsg:
                print(u"Error sending to server: %s Message %s" % (emsg[1], str(emsg[0])))
                sys.exit(-1)

        @staticmethod
        def create_socket():
            try:
                so = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            except socket.error:
                print('Error: Could not create socket...')
                sys.exit(-1)
            so.settimeout(1)
            return so

        def connect_to_server(self):
            tries = 3
            while True:
                sensor_angles = "-45 -19 -12 -7 -4 -2.5 -1.7 -1 -.5 0 .5 1 1.7 2.5 4 7 12 19 45"
                initmsg = '%s(init %s)' % (self.sid, sensor_angles)

                try:
                    self.socket.sendto(initmsg.encode(), (self.host, self.port))
                except socket.error:
                    sys.exit(-1)
                sockdata = str()

                try:
                    sockdata, address = self.socket.recvfrom(data_size)
                    sockdata = sockdata.decode('utf-8')
                except socket.error:
                    print("Waiting for server on port " + str(self.port))
                    tries -= 1
                    if tries == 0:
                        print("Server didn't answer, sending restart signal")
                        self.server.restart()

                identify = '***identified***'
                if identify in sockdata:
                    print("Client connected on port " + str(self.port))
                    break

        @staticmethod
        def encode_actions(actions):
            out = str()
            for k in actions:
                out += '(' + k + ' '
                v = actions[k]
                if not type(v) is list:
                    out += '%.3f' % v
                else:
                    out += ' '.join([str(x) for x in v])
                out += ')'
            return out

        @staticmethod
        def limit_action(v, lo, hi):
            if v < lo:
                return lo
            elif v > hi:
                return hi
            else:
                return v

        def limit_actions(self, actions):
            actions['steer'] = self.limit_action(actions['steer'], -1, 1)
            actions['brake'] = self.limit_action(actions['brake'], 0, 1)
            actions['accel'] = self.limit_action(actions['accel'], 0, 1)
            actions['clutch'] = self.limit_action(actions['clutch'], 0, 1)
            if actions['gear'] not in [-1, 0, 1, 2, 3, 4, 5, 6]:
                actions['gear'] = 0
            if actions['meta'] not in [0, 1]:
                actions['meta'] = 0
            if type(actions['focus']) is not list or min(actions['focus']) < -180 or max(
                    actions['focus']) > 180:
                actions['focus'] = 0

        def step(self, actions):
            if actions is None:
                actions = utils.get_empty_actions()

            if not self.socket:
                print('Client socket problem!')
                return
            self.limit_actions(actions)
            message = self.encode_actions(actions)
            self.send_message(message)

            return actions, self.get_server_input()

        def parse_server_string(self, server_string):
            track_data = {}
            server_string = server_string.strip()[:-1]
            server_string_list = server_string.strip().lstrip('(').rstrip(')').split(')(')
            for i in server_string_list:
                w = i.split(' ')
                track_data[w[0]] = self.destringify(w[1:])
            return track_data

        def destringify(self, string):
            if not string:
                return string
            if type(string) is str:
                try:
                    return float(string)
                except ValueError:
                    print("Could not find a value in %s" % string)
                    return string
            elif type(string) is list:
                if len(string) < 2:
                    return self.destringify(string[0])
                else:
                    return [self.destringify(i) for i in string]

        def get_server_input(self):
            sockdata = str()

            while True:
                try:
                    sockdata, address = self.socket.recvfrom(data_size)
                    sockdata = sockdata.decode('utf-8')
                except socket.error:
                    print('', end='')
                if sockdata:
                    return self.parse_server_string(sockdata)


def train(episodes, steps_per_episode):
    env = Environment()
    model = algorithm.DeepDeterministicPolicyGradient()

    actions = None
    for i in range(episodes):
        print('Episode ' + str(i + 1) + '/' + str(episodes))
        for j in range(steps_per_episode):
            # utils.print_progress(j + 1, steps_per_episode)
            actions, sensors = env.step(actions)
            env.check_sensors(sensors)
            actions = model.train_step(actions=actions, sensors=sensors)
        env.restart_environment()


if __name__ == "__main__":
    train(3, 100000)