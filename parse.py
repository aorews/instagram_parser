import instaloader
import argparse
import pickle
import sys
import time
from collections import Counter
from datetime import datetime, timedelta
from instaloader.exceptions import QueryReturnedBadRequestException
from tqdm.auto import tqdm 


class CredentialsError(Exception):
    pass

class MyRateController(instaloader.RateController):
    total_wait_time = 0

    @classmethod
    def change_context(cls, waittime):
        cls.total_wait_time += waittime
        if cls.total_wait_time > args.total_wait_429:
            cls.total_wait_time = 0
            context.get_next_context()

    def count_per_sliding_window(self, query_type):
        return 200
    
    def handle_429(self, query_type):
        """This method is called to handle a 429 Too Many Requests response.
        It calls :meth:`RateController.query_waittime` to determine the time needed to wait and then calls
        :meth:`RateController.sleep` to wait until we can repeat the same request."""
        current_time = time.monotonic()
        waittime = self.query_waittime(query_type, current_time, True)

        assert waittime >= 0
        self._dump_query_timestamps(current_time, query_type)
        text_for_429 = ("Instagram responded with HTTP error \"429 - Too Many Requests\". Please do not run multiple "
                        "instances of Instaloader in parallel or within short sequence. Also, do not use any Instagram "
                        "App while Instaloader is running.")
        self._context.error(text_for_429, repeat_at_end=False)
        if waittime > 1.5:
            formatted_waittime = ("{} seconds".format(round(waittime)) if waittime <= 666 else
                                  "{} minutes".format(round(waittime / 60)))
            self._context.error("The request will be retried in {}, at {:%H:%M}."
                                .format(formatted_waittime, datetime.now() + timedelta(seconds=waittime)),
                                repeat_at_end=False)
        if waittime > 0:
            self.sleep(waittime)

        # Changing context if 429 error is too often
        self.change_context(waittime)

class Context:
    def __init__(self):
        self.credentials = self.login_to_instagram()
        self.value = None
        self.get_next_context()

    def login_to_instagram(self):
        credentials = list()
        for username, password in args.credentials:
            try:
                L = instaloader.Instaloader(rate_controller=lambda ctx: MyRateController(ctx))
                L.login(username, password)
                credentials.append(L)
                print(f'Instagram login to {username} succeeded', file = sys.stderr)
            except:
                print(f'Instagram login to {username} failed', file = sys.stderr)
        credentials = iter(credentials)
        return credentials

    def get_next_context(self):
        creds = next(self.credentials, None)
        if creds:
            self.value = creds.context
            print(f'Instagram context changed to {self.value.username}', file = sys.stderr)
        else:
            raise CredentialsError


class Node:
    def __init__(self, id, nickname, is_ghost):
        self.id = id
        self.nickname = nickname
        self.is_ghost = is_ghost

        self.followers = None
        self.followees = None
        self.is_popular = False
        self.likes = 0

        self.not_parsed = True

    def __eq__(self, other):
        if isinstance(other, int):
            return self.id == other
        elif  self.__class__ == other.__class__:
            return self.id == other.id

    def __hash__(self):
        return self.id


class Graph:
    def __init__(self):
        self.nodes = set()
        self.edges = list()
        self.get_target_links()

    def get_target_links(self):
        profile = instaloader.Profile.from_username(context.value, args.target)
        followees = list(profile.get_followees())
        followers = list(profile.get_followers())

        for profile in followees + followers:
            self.nodes.add(Node(profile.userid, profile.username, False))
        
        return None

    def get_target_likes(self):
        profile = instaloader.Profile.from_username(context.value, args.target)
        counter = Counter()

        # Collect likes
        with tqdm(total=args.likes_threshold) as pbar:
            for post in profile.get_posts():
                if post.likes < args.likes_max_amount:
                    for like in post.get_likes():
                        counter[like.userid] += 1
                    pbar.update(post.likes)
                    if sum(counter.values()) > args.likes_threshold:
                        break

        # Assign likes for linked node
        for node in self.nodes:
            node.likes = counter.get(node.id, 0)
        
        # Assign likes for ghost node
        for node, likes in counter.items():
            if likes >= args.ghost_likes and node not in self.nodes:
                profile = instaloader.Profile.from_id(context.value, node)
                if profile.username != args.target:
                    node = Node(profile.userid, profile.username, True)
                    node.likes = likes
                    node.not_parsed = False
                    self.nodes.add(node)
       


    def get_edges(self):
        bad_request_counter = 0
        parsed_counter = 0
        for node in tqdm(self.nodes, position=0, leave=True):
            if node.not_parsed and not node.is_ghost and bad_request_counter < args.bad_request_threshold:
                if parsed_counter % 1 == 0:
                    graph.save()
                try:
                    profile = instaloader.Profile.from_id(context.value, node.id)
                    
                    node.followers = profile.followers
                    node.followees = profile.followees
                    node.is_popular = node.followers > args.star_followers

                    if node.is_popular:
                        node.not_parsed = False
                        parsed_counter += 1
                        continue
                    
                    followees = profile.get_followees()
                    for i, linked_profile in enumerate(followees):
                        if i == args.max_folowees:
                            break
                        else:
                            id = linked_profile.userid
                            if id in self.nodes:
                                self.edges.append((node.id, id))

                    node.not_parsed = False
                    parsed_counter += 1
                    
                except QueryReturnedBadRequestException:
                    bad_request_counter += 1
                except Exception as e:
                    print(e, file = sys.stderr)

        return None

    def parse_links(self):
        self.get_edges()

        while any([node.not_parsed for node in self.nodes]):
            context.get_next_context()
            self.get_edges()
        
        return None

    def save(self, path = './'):
        with open(f'{path}/{args.target}_graph.pkl', "wb" ) as f:
            pickle.dump(graph,  f)
        #print("Graph saved!", file = sys.stderr)

    @staticmethod
    def load(path):
        with open(path, "rb" ) as f:
            item = pickle.load(f)
        return item


def parse_args():
    def pair(arg):
        arg = [x for x in arg.split(',')]
        if arg[0] == '' or arg[1] == '':
            raise Exception('Incorrect credentials')
        return arg

    parser = argparse.ArgumentParser('Provide instagram credentials and target username')
    parser.add_argument('--credentials', type = pair, nargs = '+',required = True, help = 'Provide one or multiple pairs of login and password separated by comma. For example login1,password1 login2,password2')
    parser.add_argument('--target', type = str, required = True, help = 'Provide target instagram username')
    parser.add_argument('--max_folowees', type = int, nargs = '?', default = 500, help = 'Maximum amount of folowees to parse to gather links between nodes')
    parser.add_argument('--star_followers', type = int, nargs = '?', default = 5000, help = 'Minimum amount of followers to skip node and consider it star')
    parser.add_argument('--bad_request_threshold', type = int, nargs = '?', default = 10, help = 'BadRequest error raised whenever instagram blocks current credentials. Threshold is provided to allow unexpected errors.')
    parser.add_argument('--total_wait_429', type = int, nargs = '?', default = 20*60, help = 'Amount of seconds to wait with 429 error before changing context')
    parser.add_argument('--likes_max_amount', type = int, nargs = '?', default = 500, help = 'Maximum amount of likes on one post to parse it')
    parser.add_argument('--likes_threshold', type = int, nargs = '?', default = 5000, help = 'Maximum amount of parsed likes')
    parser.add_argument('--ghost_likes', type = int, nargs = '?', default = 5, help = 'Amount of likes from neither followed nor followee user to add it to graph.')
    parser.add_argument('--load_state', type = str, help = 'Path to saved graph')
    #'--credentials login,pass --target target --load_state path'.split()
    return parser.parse_args()


if __name__ == '__main__':    
    args = parse_args()

    try:
        print("Instagram login", file = sys.stderr)
        context = Context()
        
        if args.load_state:
             graph = Graph.load(args.load_state)
             print('State loaded')
        else:
            print(f'Collecting {args.target} followers and followees', file = sys.stderr)
            graph = Graph()
            print(f'Parsing target likes', file = sys.stderr)
            graph.get_target_likes()

        print(f'Parsing target links', file = sys.stderr)
        graph.parse_links()

        print(f'Saving parsed data', file = sys.stderr)
        graph.save()
        
    except CredentialsError:
        print("No working credentials left, quitting", file = sys.stderr)
        graph.save()
    except Exception as e:
        print(e, file = sys.stderr)
        graph.save()
