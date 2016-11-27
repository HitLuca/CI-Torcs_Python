import json
import os
from time import sleep
import numpy as np

from ddpg_torcs import DDPGTorcs
from utilities.reward_writer import RewardWriter

TRACK_LIST = {'aalborg': 'road',
              'alpine-1': 'road',
              'alpine-2': 'road',
              'brondehach': 'road',
              'corkscrew': 'road',
              'eroad': 'road',
              'e-track-1': 'road',
              'e-track-2': 'road',
              'e-track-3': 'road',
              'e-track-4': 'road',
              'e-track-6': 'road',
              'forza': 'road',
              'g-track-1': 'road',
              'g-track-2': 'road',
              'g-track-3': 'road',
              'ole-road-1': 'road',
              'ruudskogen': 'road',
              'spring': 'road',
              'street-1': 'road',
              'wheel-1': 'road',
              'wheel-2': 'road',
              'a-speedway': 'oval',
              'b-speedway': 'oval',
              'c-speedway': 'oval',
              'd-speedway': 'oval',
              'e-speedway': 'oval',
              'e-track-5': 'oval',
              'f-speedway': 'oval',
              'g-speedway': 'oval',
              'michigan': 'oval',
              'dirt-1': 'dirt',
              'dirt-2': 'dirt',
              'dirt-3': 'dirt',
              'dirt-4': 'dirt',
              'dirt-5': 'dirt',
              'dirt-6': 'dirt',
              'mixed-1': 'dirt',
              'mixed-2': 'dirt'}


class TrackUtilities:
    @staticmethod
    def create_complete_tracks_list(epsilons):
        tracks = {}
        for epsilon in epsilons:
            tracks[str(epsilon)] = []
        for epsilon in epsilons:
            for track in TRACK_LIST.keys():
                if TRACK_LIST[track] != 'dirt':
                    if track != 'b-speedway' and track != 'c-speedway' and track != 'd-speedway' and track != 'e-speedway' and track != 'f-speedway' and track != 'g-speedway':
                        tracks[str(epsilon)].append(track)
        return tracks

    @staticmethod
    def save_remaining_tracks(tracks, filepath):
        with open(filepath, 'w+') as f:
            json.dump(tracks, f, sort_keys=True, indent=4)

    @staticmethod
    def load_tracks(track_filename):
        if os.path.isfile(track_filename):
            with open(track_filename, 'r') as f:
                return json.load(f)
        else:
            return False

    @staticmethod
    def load_last_network_path(track_filename):
        if os.path.isfile(track_filename):
            with open(track_filename) as f:
                network_name = f.readline().replace('\n', '')
                i = f.readline()
                return network_name, int(i)
        else:
            return '', 0

    @staticmethod
    def save_last_network_path(last_network_file_path, save_file_path, i):
        with open(last_network_file_path, 'w+') as f:
            print(save_file_path, file=f)
            print(str(i), file=f)

    @staticmethod
    def order_tracks(tracks):
        for key in tracks.keys():
            tracks[key].sort()

    @staticmethod
    def train_on_all_tracks(root_dir='all_tracks'):
        # This is used if you want to restart everything but you want to have a trained network at the start
        start_with_trained_network = False

        root_dir = 'runs/' + root_dir + '/'

        epsilons = [0.5, 0.1, 0]
        tracks_to_test = root_dir + 'tracks_to_test.json'
        network_filepath = root_dir + 'trained_networks/test_'
        last_network_filepath = root_dir + 'trained_networks/last_network.txt'
        tracks_to_test_filepath = root_dir + 'tracks_to_test.json'
        rewards_filepath = root_dir + 'rewards.csv'

        reward_writer = RewardWriter(rewards_filepath)

        tracks = TrackUtilities.load_tracks(tracks_to_test)
        if not tracks:
            tracks = TrackUtilities.create_complete_tracks_list(epsilons)
        TrackUtilities.order_tracks(tracks)

        # load the right network
        if start_with_trained_network:
            load_filepath = 'trained_networks/pre_trained.h5f'
            i = 0
        else:
            load_filepath, i = TrackUtilities.load_last_network_path(last_network_filepath)

        save_filepath = load_filepath

        for epsilon in epsilons:
            while len(tracks[str(epsilon)]) > 0:
                track = tracks[str(epsilon)][0]

                if i != 0:
                    load_filepath = save_filepath
                save_filepath = network_filepath + str(i) + '_' + track + '_' + str(epsilon) + '.h5f'

                print('Track name:', track)
                print('Epsilon:', epsilon)
                print()

                # write track name
                reward_writer.write_track(track, epsilon)

                try:
                    DDPGTorcs.train(reward_writer, load=True, gui=True, save=True, track=track, nb_steps=100000,
                                    load_file_path=load_filepath, save_file_path=save_filepath, verbose=1,
                                    timeout=40000,
                                    epsilon=epsilon)

                    i += 1
                    tracks[str(epsilon)].remove(track)
                    TrackUtilities.save_remaining_tracks(tracks, tracks_to_test_filepath)
                    TrackUtilities.save_last_network_path(last_network_filepath, save_filepath, i)

                    reward_writer.completed_track()
                except:
                    # Torcs fucked up, so now we fix everything
                    save_file_path = load_filepath
                    reward_writer.bad_run()
                    reward_writer.completed_track()

    @staticmethod
    def train_on_single_track(root_dir, track='aalborg', epsilon=0.5, steps=500000, load=False, load_filepath='',
                              noise=1, max_speed=None, n_lap=None):
        root_dir = 'runs/' + root_dir
        rewards_filepath = root_dir + '/rewards.csv'

        gui = True
        save = True

        if not os.path.exists(root_dir):
            os.makedirs(root_dir)

        reward_writer = RewardWriter(rewards_filepath)
        save_file_path = root_dir + '/' + track + '_' + str(epsilon) + '.h5f'

        reward_writer.write_track(track, epsilon)
        print('Track name:', track)
        print('Epsilon:', epsilon)

        DDPGTorcs.train(reward_writer, load=load, gui=gui, save=save, track=track, nb_steps=steps,
                        load_file_path=load_filepath,
                        save_file_path=save_file_path, verbose=1, timeout=40000, epsilon=epsilon, noise=noise, max_speed=max_speed, n_lap=n_lap)

        reward_writer.completed_track()
        print()
        print()

    def curriculum_learning_on_track(self, track,root_dir, initial_speed=30, initial_epsilon=0.5):
        speed = initial_speed
        epsilon = initial_epsilon

        def action_limit_function(speed, action, observation):
            if observation[21] * 300 > speed:
                action[1] -= 1.5
            return action

        root_dir = 'runs/' + root_dir + '/'
        rewards_filepath = root_dir + 'rewards.csv'
        remaining_tracks_filepath = root_dir + 'tracks_to_test.json'
        last_network_filepath = root_dir + 'last_network.txt'

        if not os.path.exists(root_dir):
            os.makedirs(root_dir)
            load_filepath = ''
            i = 0
        else:
            load_filepath, i = TrackUtilities.load_last_network_path(last_network_filepath)

        reward_writer = RewardWriter(rewards_filepath)

        save_filepath = load_filepath

        while speed < 350:
            # try:
            load_filepath = save_filepath
            save_filepath = root_dir + str(i) + '_' + track + '_speed' + str(speed) + '.h5f'

            reward_writer.write_track(track, epsilon)

            print('Epsilon:', epsilon)
            DDPGTorcs.train(reward_writer, load=True, gui=True, save=True, track=track,
                            load_file_path=load_filepath, save_file_path=save_filepath,
                            verbose=1, timeout=40000, epsilon=epsilon, action_limit_function=lambda a, s: action_limit_function(speed,a,s), nb_steps=1000000,
                            nb_max_episode_steps=1000000, n_lap=2)

            reward_writer.completed_track()
            print()
            print()
            # except:
            #     pass
            speed += 5
            #epsilon *= 0.9



    @staticmethod
    def create_tracks_list(chosen_tracks, epsilons):
        tracks = {}
        for epsilon in epsilons:
            tracks[str(epsilon)] = []
            for track in chosen_tracks:
                tracks[str(epsilon)].append(track)
        return tracks

    @staticmethod
    def train_on_chosen_tracks(chosen_tracks, epsilons, steps, root_dir):
        root_dir = 'runs/' + root_dir + '/'
        rewards_filepath = root_dir + 'rewards.csv'
        remaining_tracks_filepath = root_dir + 'tracks_to_test.json'
        last_network_filepath = root_dir + 'last_network.txt'

        if not os.path.exists(root_dir):
            os.makedirs(root_dir)
            load_filepath = ''
            i = 0
        else:
            load_filepath, i = TrackUtilities.load_last_network_path(last_network_filepath)

        reward_writer = RewardWriter(rewards_filepath)

        tracks = TrackUtilities.load_tracks(remaining_tracks_filepath)
        if not tracks:
            tracks = TrackUtilities.create_tracks_list(chosen_tracks, epsilons)
        TrackUtilities.order_tracks(tracks)

        save_filepath = load_filepath

        for epsilon in epsilons:
            while len(tracks[str(epsilon)]) > 0:
                track = tracks[str(epsilon)][0]

                load_filepath = save_filepath
                save_filepath = root_dir + str(i) + '_' + track + '_' + str(epsilon) + '.h5f'

                reward_writer.write_track(track, epsilon)

                print('Track name:', tracks[str(epsilon)][0])
                print('Epsilon:', epsilon)

                DDPGTorcs.train(reward_writer, load=True, gui=True, save=True, track=track,
                                nb_steps=steps, load_file_path=load_filepath, save_file_path=save_filepath,
                                verbose=1, timeout=40000, epsilon=epsilon)

                tracks[str(epsilon)].remove(track)
                i += 1
                TrackUtilities.save_remaining_tracks(tracks, remaining_tracks_filepath)
                TrackUtilities.save_last_network_path(last_network_filepath, save_filepath, i)
                reward_writer.completed_track()
                print()
                print()

    @staticmethod
    def test_network(track, load_filepath):
        DDPGTorcs.test(None, load_filepath, track=track)
