from abc import ABC, abstractmethod
from datetime import datetime

class ActionInterface(ABC):

    def do_action(self):
        pass

    def do_action(self, start: datetime, end: datetime):
        pass
