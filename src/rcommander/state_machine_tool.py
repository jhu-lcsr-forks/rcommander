#import roslib; roslib.load_manifest('rcommander_core')
import rospy
from PyQt4.QtGui import *
from PyQt4.QtCore import *
import tool_utils as tu
import smach
import os.path as pt
import graph_model as gm


class StateMachineTool(tu.ToolBase):

    def __init__(self, rcommander):
        tu.ToolBase.__init__(self, rcommander, 'state_machine', 'State Machine', StateMachineNode)
        self.child_gm = None

    def fill_property_box(self, pbox):
        formlayout = pbox.layout()
        self.filename_edit = QLineEdit(pbox)
        self.filename_edit.setText("...")
        self.open_file_button = QPushButton(pbox)
        self.open_file_button.setText('Select...')
        self.rcommander.connect(self.open_file_button, SIGNAL('clicked()'), self.open_file_cb)

        formlayout.addRow('&Filename', self.filename_edit)
        formlayout.addRow(self.open_file_button)

    def open_file_cb(self):
        dialog = QFileDialog(self.rcommander, 'Open State Machine', '~')
        dialog.setFileMode(QFileDialog.Directory)
        dialog.setViewMode(QFileDialog.List)

        #Fix messed up bug, weird interaction between file dialog and rospy!
        import rospy.core as rpc
        rpc._shutdown_flag = False

        if dialog.exec_():
            filenames = dialog.selectedFiles()
            filename = str(filenames[0])
            self.filename_edit.setText(filename)

    def new_node(self, name=None):
        child_gm = self.child_gm
        self.child_gm = None

        if (child_gm == None) and (str(self.filename_edit.text()) != '...'):
            #nname = pt.split(str(self.filename_edit.text()))[1]
            print 'state machine tool loading', self.filename_edit.text()
            child_gm = gm.GraphModel.load(str(self.filename_edit.text()))
            #curr_document = gm.FSMDocument(child_gm.get_document().get_name(), modified=True, real_filename=False)
            curr_document = gm.FSMDocument(name, modified=True, real_filename=False)
            child_gm.set_document(curr_document)
        else:
            if child_gm != None:
                curr_document = gm.FSMDocument(name, modified=True, real_filename=False)
                child_gm.set_document(curr_document)
                return StateMachineNode(name, child_gm)
            if name == None:
                nname = self.name + str(self.counter)
                return StateMachineNode(nname, None)
            else:
                #raise RuntimeError('Need to specify filename.')
                return None

        return StateMachineNode(name, child_gm)

    def set_node_properties(self, my_node):
        self.child_gm = my_node.child_gm
        if self.child_gm == None:
            return
        if self.child_gm.get_document() != None:
            fname = self.child_gm.get_document().get_filename()
            if fname != None:
                self.filename_edit.setText(fname)

    def reset(self):
        self.filename_edit.setText("...")
        self.child_gm = None


class StateMachineNode(tu.EmbeddableState):

    def __init__(self, name, child_gm):
        tu.EmbeddableState.__init__(self, name, child_gm)

    def get_smach_state(self):
        return StateMachineNodeSmach(self.child_gm)

    def recreate(self, graph_model):
        #return StateMachineNode(graph_model.document.get_name(), graph_model)
        return StateMachineNode(self.get_name(), graph_model)

class StateMachineNodeSmach(smach.State):

    def __init__(self, child_gm):
        self.child_gm = child_gm

    def set_robot(self, robot):
        self.robot = robot
        input_keys = []
        output_keys = []
        outcomes = []
        if self.child_gm != None:
            sm = self.child_gm.create_state_machine(robot)
            input_keys = list(sm.get_registered_input_keys())
            output_keys = list(sm.get_registered_output_keys())
            outcomes = list(sm.get_registered_outcomes()) + ['preempted']
        smach.State.__init__(self, outcomes = outcomes, input_keys = input_keys, output_keys = output_keys)


    def execute(self, userdata):
        child_gm = self.child_gm
        sm = child_gm.create_state_machine(self.robot, userdata=userdata._ud)
        child_gm.run(self.child_gm.get_start_state(), state_machine=sm)
        rthread = child_gm.sm_thread['run_sm']

        preempted = False
        r = rospy.Rate(30)
        while True:
            if rthread.exception != None:
                raise rthread.exception

            if rthread.outcome != None:
                rospy.loginfo('State Machine Node: child node finished with outcome ' + rthread.outcome)
                break

            if not rthread.isAlive():
                rospy.loginfo('State Machine Node: child node died')
                break

            if self.preempt_requested():
                rospy.loginfo('State Machine Node: preempt requested')
                rthread.preempt()
                self.service_preempt()
                preempted = True
                break

            r.sleep()

        #child_gm.sm_thread = {} #Reset sm thread dict
        if preempted:
            return 'preempted'
        else:
            return rthread.outcome


###
## need to be able to generate state machines
## act as a smach state, like gripper event but does nothing else beside execute state machine
## TODO: maybe we can recognize this special case in graph model and add its child state machine directly during compilation?
#class StateMachineNode(smach.State, tu.EmbeddableState): 
#
#    def __init__(self, name, child_gm):
#        tu.EmbeddableState.__init__(self, name, child_gm)
#        self.__init_unpicklables__()
#
#    def __init_unpicklables__(self):
#        #Init smach stuff
#        input_keys = []
#        output_keys = []
#        outcomes = []
#
#        if self.get_child() != None:
#            sm = self.get_child().create_state_machine()
#            input_keys = list(sm.get_registered_input_keys())
#            output_keys = list(sm.get_registered_output_keys())
#            outcomes = list(sm.get_registered_outcomes())         
#        smach.State.__init__(self, outcomes = outcomes, input_keys = input_keys, output_keys = output_keys)
#
#    def execute(self, userdata):
#        child_gm = self.get_child()
#        sm = child_gm.create_state_machine(userdata=userdata._ud)
#        child_gm.run(self.child_gm.get_start_state(), state_machine=sm)
#        rthread = child_gm.sm_thread['run_sm']
#
#        preempted = False
#        r = rospy.Rate(100)
#        while True:
#            if rthread.exception != None:
#                raise rthread.exception
#
#            if rthread.outcome != None:
#                rospy.loginfo('State Machine Node: child node finished with outcome ' + rthread.outcome)
#                break
#
#            if not rthread.isAlive():
#                rospy.loginfo('State Machine Node: child node died')
#                break
#
#            if self.preempt_requested():
#                rospy.loginfo('State Machine Node: preempt requested')
#                self.service_preempt()
#                preempted = True
#                break
#
#        rthread.preempt()
#        rthread.except_preempt()
#        child_gm.sm_thread = {} #Reset sm thread dict
#        if preempted:
#            return 'preempted'
#        else:
#            return rthread.outcome
#
#    def recreate(self, graph_model):
#        return StateMachineNode(graph_model.document.get_name(), graph_model)
#
#    def __getstate__(self):
#        state = tu.EmbeddableState.__getstate__(self)
#        return {'state_base': state}
#
#    def __setstate__(self, state):
#        tu.EmbeddableState.__setstate__(self, state['state_base'])
#        self.__init_unpicklables__()


