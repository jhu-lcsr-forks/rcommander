#import roslib; roslib.load_manifest('rcommander_core')
import rospy
from PyQt4.QtGui import *
from PyQt4.QtCore import *
import tool_utils as tu
import smach

class SleepTool(tu.ToolBase):

    def __init__(self, rcommander):
        tu.ToolBase.__init__(self, rcommander, 'sleep', 'Sleep', SleepState)

    def fill_property_box(self, pbox):
        formlayout = pbox.layout()
        self.time_box = QDoubleSpinBox(pbox)
        self.time_box.setMinimum(0)
        self.time_box.setMaximum(1000.)
        self.time_box.setSingleStep(.2)
        self.time_box.setValue(3.)
        formlayout.addRow("&Seconds", self.time_box)

    def new_node(self, name=None):
        if name == None:
            nname = self.name + str(self.counter)
        else:
            nname = name
        return SleepState(nname, self.time_box.value())

    def set_node_properties(self, my_node):
        self.time_box.setValue(my_node.sleep_time)

    def reset(self):
        self.time_box.setValue(3.)

class SleepState(tu.StateBase):

    def __init__(self, name, sleep_time):
        tu.StateBase.__init__(self, name)
        self.sleep_time = sleep_time

    def get_smach_state(self):
        return SleepSmachState(self.sleep_time)

class SleepSmachState(smach.State):

    def __init__(self, sleep_time):
        smach.State.__init__(self, outcomes=['preempted', 'done'], input_keys=[], output_keys=[])
        self.sleep_time = sleep_time

    def execute(self, userdata):
        r = rospy.Rate(30)
        start_time = rospy.get_time()
        while (rospy.get_time() - start_time) < self.sleep_time:
            r.sleep()
            if self.preempt_requested():
                self.services_preempt()
                return 'preempted'
        return 'done'
#class SleepState(smach.State, tu.StateBase): 
#
#    def __init__(self, name, sleep_time):
#        self.__init_unpicklables__()
#
#    def execute(self, userdata):
#        rospy.sleep(self.sleep_time)
#        return 'done'
#
#    def __init_unpicklables__(self):
#        tu.StateBase.__init__(self, self.name)
#        smach.State.__init__(self, outcomes = ['done'], input_keys = [], output_keys = [])
#
#    def __getstate__(self):
#        state = tu.StateBase.__getstate__(self)
#        my_state = [self.name, self.sleep_time]
#        return {'state_base': state, 'self': my_state}
#
#    def __setstate__(self, state):
#        tu.StateBase.__setstate__(self, state['state_base'])
#        self.name, self.sleep_time = state['self']
#        self.__init_unpicklables__()



