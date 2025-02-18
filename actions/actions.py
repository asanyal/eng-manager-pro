from abc import ABC, abstractmethod

class ActionInterface(ABC):

    def do_action(self):
        pass

    def do_action(self, start, end):
        pass
