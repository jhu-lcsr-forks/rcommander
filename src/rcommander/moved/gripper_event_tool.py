import roslib; roslib.load_manifest('rcommander')
import rospy
from PyQt4.QtGui import *
from PyQt4.QtCore import *
import pr2_gripper_sensor_msgs.msg as gr
import actionlib_msgs.msg as am
import actionlib
import tool_utils as tu
import smach
import graph_model as gm
import sm_thread_runner as smtr

class GripperEventTool(tu.ToolBase):

    def __init__(self, rcommander):
        tu.ToolBase.__init__(self, rcommander, 'gripper_event', 'Gripper Event')
        self.child_gm = None

    #NEED TO IMPLEMENT
    def get_smach_class(self):
        return GripperEventState

    #NEED TO IMPLEMENT
    def set_child_node(self, child_smach):
        self.child_gm = gm.GraphModel()
        self.child_gm.add_node(child_smach)
        self.child_gm.set_start_state(child_smach.get_name())
        self.child_gm.set_document(gm.FSMDocument(child_smach.get_name(), modified=False, real_filename=False))

    def fill_property_box(self, pbox):
        formlayout = pbox.layout()

        self.gripper_radio_boxes, self.gripper_radio_buttons = tu.make_radio_box(pbox, ['Left', 'Right'], 'gripper_event_arm')
        self.event_box = QComboBox(pbox)
        for event in GripperEventState.EVENT_LIST:
            self.event_box.addItem(event)
        self.accel_box = tu.SliderBox(pbox, 8.25, 30, 0., .25, 'gripper_accel', units='m/s^2')
        self.slip_box = tu.SliderBox(pbox, .01, -.5, .5, .1, 'gripper_slip', units='')

        formlayout.addRow('&Gripper', self.gripper_radio_boxes)
        formlayout.addRow('&Event', self.event_box)
        formlayout.addRow('&Acceleration', self.accel_box.container)
        formlayout.addRow('&Slip', self.slip_box.container)
        pbox.update()

    def _create_node(self, name=None):
        if self.child_gm == None:
            raise RuntimeError('No child node!')
        selected_arm = None
        for r in self.gripper_radio_buttons:
            if r.isChecked():
                selected_arm = str(r.text()).lower()
        if selected_arm == None:
            raise RuntimeError('No arm selected!')

        event_type = str(self.event_box.currentText())
        accel_val = self.accel_box.value()
        slip_val = self.slip_box.value()

        if name == None:
            nname = self.name + str(self.counter)
        else:
            nname = name

        return GripperEventState(nname, self.child_gm, selected_arm, event_type, accel_val, slip_val)
    
    def _node_selected(self, gripper_event_state):
        if gripper_event_state.arm == 'left':
            self.gripper_radio_buttons[0].setChecked(True)
        if gripper_event_state.arm == 'right':
            self.gripper_radio_buttons[1].setChecked(True)

        self.event_box.setCurrentIndex(self.event_box.findText(gripper_event_state.event_type))
        self.accel_box.set_value(gripper_event_state.accel)
        self.slip_box.set_value(gripper_event_state.slip)
        self.child_gm = gripper_event_state.child_gm

        #self.child_node = gripper_event_state.get_child()

    def reset(self):
        self.gripper_radio_buttons[0].setChecked(True)
        self.event_box.setCurrentIndex(self.event_box.findText(GripperEventState.EVENT_LIST[0]))
        self.accel_box.set_value(8.25)
        self.slip_box.set_value(.01)
        self.child_gm = None


class GripperEventState(smach.State, tu.EmbeddableState): 

    EVENT_LIST = ['acceleration', 'slip', 'finger side impact or acceleration', 'slip and acceleration', 'finger side impact, slip or acceleration']
    EVENT_CODES = {'acceleration':                             gr.PR2GripperEventDetectorCommand.ACC,
                   'slip':                                     gr.PR2GripperEventDetectorCommand.SLIP,
                   'finger side impact or acceleration':       gr.PR2GripperEventDetectorCommand.FINGER_SIDE_IMPACT_OR_ACC,
                   'slip and acceleration':                    gr.PR2GripperEventDetectorCommand.SLIP_AND_ACC,
                   'finger side impact, slip or acceleration': gr.PR2GripperEventDetectorCommand.FINGER_SIDE_IMPACT_OR_SLIP_OR_ACC}
    EVENT_OUTCOME = 'detected_event'

    def __init__(self, name, child_gm, arm, event_type, accel, slip):
        tu.EmbeddableState.__init__(self, name, child_gm)
        self.arm = arm
        self.event_type = event_type
        self.accel = accel
        self.slip = slip
        self.__init_unpicklables__() 

    def __init_unpicklables__(self):
        #Init smach stuff
        input_keys = []
        output_keys = []
        outcomes = []

        if self.get_child() != None:
            sm = self.get_child().create_state_machine()
            input_keys = list(sm.get_registered_input_keys())
            output_keys = list(sm.get_registered_output_keys())
            outcomes = list(sm.get_registered_outcomes()) + [GripperEventState.EVENT_OUTCOME]
        smach.State.__init__(self, outcomes = outcomes, input_keys = input_keys, output_keys = output_keys)

        #Setup our action server
        if self.arm == 'left':
            a = 'l'
        elif self.arm == 'right':
            a = 'r'
        else:
            raise RuntimeError('Error')
        evd_name = a + '_gripper_sensor_controller/event_detector'
        self.action_client = actionlib.SimpleActionClient(evd_name, gr.PR2GripperEventDetectorAction)

    #Can't pickle graph models, have to have other mechanisms saving it
    def __getstate__(self):
        state = tu.EmbeddableState.__getstate__(self)
        my_state = [self.arm, self.event_type, self.accel, self.slip]
        return {'embeddable': state, 'self': my_state}

    #Can't pickle graph models, have to have other mechanisms saving it
    def __setstate__(self, state):
        tu.EmbeddableState.__setstate__(self, state['embeddable'])
        self.arm, self.event_type, self.accel, self.slip = state['self']
        self.__init_unpicklables__()

    #must implement in embeddable nodes
    def recreate(self, new_graph_model):
        return GripperEventState(self.name, new_graph_model, self.arm, self.event_type, self.accel, self.slip)

    def _detected_event(self):
        state = self.action_client.get_state()
        gripper_event_detected = state not in [am.GoalStatus.ACTIVE, am.GoalStatus.PENDING]
        return gripper_event_detected

    def execute(self, userdata):
        print '>> executing, got userdata:', userdata, 'keys', userdata.keys()
        print 'input keys', self.get_registered_input_keys(), 'ud_keys', userdata._ud.keys()
        rospy.sleep(2)

        goal = gr.PR2GripperEventDetectorGoal()
        goal.command.acceleration_trigger_magnitude = self.accel
        goal.command.slip_trigger_magnitude = self.slip
        goal.command.trigger_conditions = GripperEventState.EVENT_CODES[self.event_type]
        #print 'ge: sending goal'
        self.action_client.send_goal(goal)

        #Let state machine execute, but kill its thread if we detect an event
        #print 'ge: creating sm and running'
        child_gm = self.get_child()
        #self.child = child_gm

        #print dir(userdata)
        sm = child_gm.create_state_machine(userdata=userdata._ud)
        #child_gm.run(self.child_smach_node.get_name(), state_machine=sm)
        child_gm.run(self.child_gm.get_start_state(), state_machine=sm)
        rthread = child_gm.sm_thread['run_sm']

        #rthread = smtr.ThreadRunSM(self.child_smach_node.get_name(), sm)
        #rthread.start()

        
        event = self._detected_event()
        preempted = False
        r = rospy.Rate(100)
        while not event:
            if rthread.exception != None:
                raise rthread.exception

            if rthread.outcome != None:
                rospy.loginfo('Gripper Event Tool: child node finished with outcome ' + rthread.outcome)
                break

            if not rthread.isAlive():
                rospy.loginfo('Gripper Event Tool: child node died')
                break

            if self.preempt_requested():
                rospy.loginfo('Gripper Event Tool: preempt requested')
                self.service_preempt()
                preempted = True
                break

            event = self._detected_event() 
            if event:
                rospy.loginfo('Gripper Event Tool: DETECTED EVENT')

            r.sleep()

        #print 'ge: sm finished'

        #send preempt to whatever is executing
        rthread.preempt()
        rthread.except_preempt()
        #self.child_gm = None
        child_gm.sm_thread = {} #Reset sm thread dict

        if preempted:
            return 'preempted'

        if event:
            return self.EVENT_OUTCOME
        else:
            #reverse look up child outcome
            #for outcome, outcome_rename in child_gm.current_children_of(self.child_smach_node.name):
            #TODO look at this
            #for outcome, outcome_rename in child_gm.current_children_of(self.get_child_name()):
            #    if outcome_rename == rthread.outcome:
            #        return outcome
            #if not found just return what we have
            return rthread.outcome






#from pr2_gripper_sensor_msgs.msg import PR2GripperFindContactAction, PR2GripperFindContactGoal, \
#    PR2GripperGrabAction, PR2GripperGrabGoal, PR2GripperEventDetectorAction, PR2GripperEventDetectorGoal

#whicharm = 'r'
#evd_client = actionlib.SimpleActionClient(evd_name, gr.PR2GripperEventDetectorAction)
#
#goal = PR2GripperEventDetectorGoal()
#goal.command.acceleration_trigger_magnitude = accel
#goal.command.slip_trigger_magnitude = slip
#goal.command.trigger_conditions = goal.command.ACC
#goal.command.trigger_conditions = goal.command.SLIP
#goal.command.trigger_conditions = goal.command.FINGER_SIDE_IMPACT_OR_ACC
#goal.command.trigger_conditions = goal.command.SLIP_AND_ACC
#goal.command.trigger_conditions = goal.command.FINGER_SIDE_IMPACT_OR_SLIP_OR_ACC 

#Either detect event or not
#evd_client.send_goal(goal)
#evd_client.wait_for_result()
#state = evd_client.get_state()
#if state == am.GoalStatus.SUCCEEDED:

