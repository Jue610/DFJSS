import numpy as np
import sys
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import brain_machine_S as brain
import sequencing

class DRL_sequencing(brain.sequencing_brain):
    def __init__(self, env, machine_list, job_creator, *args, **kwargs):
        # initialize the environment and the workcenter to be controlled
        self.env = env
        # get list of alll machines, for collecting the global data
        self.m_list = machine_list
        self.job_creator = job_creator
        # each item is a network
        self.net_dict = {}
        self.kwargs = kwargs
        '''
        choose the trained parameters by its reward function
        '''
        if 'reward_function' in kwargs:
            pass
        else:
            print('WARNING: reward function is not specified')
            raise Exception
        # build action NN for each target machine
        if 'Norm' in kwargs and kwargs['Norm']:
            print("---> Normalization mode ON <---")
            self.address_seed ="{}\\sequencing_models\\Norm_rwd"+str(kwargs['reward_function'])+"_{}.pt"
            self.func_list = [sequencing.SPT,sequencing.WINQ,sequencing.MS,sequencing.CR]
            self.output_size = len(self.func_list)
            for m in self.m_list:
                # adaptive input size
                self.input_size = len(self.state_normalization(self.m_list[0].sequencing_data_generation()))
                # build a network
                self.net_dict[m.m_idx] = trained_network_normalization(self.input_size, self.output_size, 3, 9)
                # retrive the parameters
                self.net_dict[m.m_idx].net.load_state_dict(torch.load(self.address_seed.format(sys.path[0],str(m.m_idx))))
                # just in case
                self.net_dict[m.m_idx].eval()  # must have this if you're loading a model, unnecessray for loading state_dict
                # take over the target machine's sequencing function
                m.job_sequencing = self.action_by_DRL
                self.build_state = self.state_normalization
        elif 'MC' in kwargs and kwargs['MC']:
            print("---> Multi-Channel (MC) mode ON <---")
            self.func_list = [sequencing.SPT,sequencing.WINQ,sequencing.MS,sequencing.CR]
            self.output_size = len(self.func_list)
            self.address_seed = "{}\\sequencing_models\\MC_rwd"+str(kwargs['reward_function'])+"_{}.pt"
            self.input_size = len(self.state_multi_channel(self.m_list[0].sequencing_data_generation()))
            # build a network
            self.network = brain.network_multi_channel(self.input_size, self.output_size)
            # retrive the parameters
            self.network.network.load_state_dict(torch.load(self.address_seed.format(sys.path[0])))
            # just in case
            self.network.eval()  # must have this if you're loading a model, unnecessray for loading state_dict
            self.build_state = self.state_multi_channel
            for m in self.m_list:
                m.job_sequencing = self.action_sqc_rule
        elif 'MR' in kwargs and kwargs['MR']:
            print("---X Minimal repetition (direct) mode ON X---")
            self.address_seed = "{}\\sequencing_models\\MR_direct_rwd"+str(kwargs['reward_function'])+".pt"
            self.input_size =  self.state_direct(self.m_list[0].sequencing_data_generation()).size()
            self.input_size_as_list = list(self.input_size)
            self.output_size = 4
            # build a network
            self.network = brain.network_value_based(self.input_size, self.output_size)
            # retrive the parameters
            self.network.network.load_state_dict(torch.load(self.address_seed.format(sys.path[0])))
            # just in case
            self.network.eval()  # must have this if you're loading a model, unnecessray for loading state_dict
            self.build_state = self.state_direct
            for m in self.m_list:
                m.job_sequencing = self.action_direct
        elif 'validated' in kwargs and kwargs['validated']:
            print("---> VALIDATION <---")
            self.func_list = [sequencing.SPT,sequencing.WINQ,sequencing.MS,sequencing.CR]
            self.output_size = len(self.func_list)
            if self.job_creator.pt_range[1]/self.job_creator.pt_range[0] > 2.5:
                scenario = "H"
            else:
                scenario = 'L'
            if self.job_creator.tightness==2:
                scenario += "H"
            else:
                scenario += 'L'
            try:
                scenario += str(kwargs['reward_function'])
            except:
                pass
            self.address_seed = "{}\\sequencing_models\\validated_" + scenario + ".pt"
            self.input_size = len(self.state_multi_channel(self.m_list[0].sequencing_data_generation()))
            self.network = brain.network_validated(self.input_size, self.output_size)
            self.network.network.load_state_dict(torch.load(self.address_seed.format(sys.path[0])))
            self.network.eval()  # must have this if you're loading a model, unnecessray for loading state_dict
            self.build_state = self.state_multi_channel
            for m in self.m_list:
                m.job_sequencing = self.action_sqc_rule
        elif 'ext_validated' in kwargs and kwargs['ext_validated']:
            print("---> EXTENDED VALIDATION <---")
            self.func_list = [sequencing.SPT,sequencing.WINQ,sequencing.MS,sequencing.CR]
            self.output_size = len(self.func_list)
            if self.job_creator.pt_range[1]/self.job_creator.pt_range[0] > 2.5:
                scenario = "H"
            else:
                scenario = 'L'
            if self.job_creator.tightness==2:
                scenario += "H"
            else:
                scenario += 'L'
            try:
                scenario += str(kwargs['reward_function'])
            except:
                pass
            self.address_seed = "{}\\sequencing_models\\validated_" + scenario + "_ext{}.pt".format(self.job_creator.no_wcs)
            self.input_size = len(self.state_multi_channel(self.m_list[0].sequencing_data_generation()))
            self.network = brain.network_validated(self.input_size, self.output_size)
            self.network.network.load_state_dict(torch.load(self.address_seed.format(sys.path[0])))
            self.network.eval()  # must have this if you're loading a model, unnecessray for loading state_dict
            self.build_state = self.state_multi_channel
            for m in self.m_list:
                m.job_sequencing = self.action_sqc_rule
        elif 'MR_validated' in kwargs and kwargs['MR_validated']:
            print("---> Validated Minimal repetition mode <---")
            no_ops = len(self.job_creator.wc_list)
            self.address_seed = "{}\\sequencing_models\\MR_validated_" + str(no_ops) + "ops.pt"
            self.input_size =  self.state_direct(self.m_list[0].sequencing_data_generation()).size()
            self.input_size_as_list = list(self.input_size)
            self.output_size = 4
            self.network = brain.network_value_based(self.input_size, self.output_size)
            self.network.network.load_state_dict(torch.load(self.address_seed.format(sys.path[0])))
            self.network.eval()  # must have this if you're loading a model, unnecessray for loading state_dict
            self.build_state = self.state_direct
            for m in self.m_list:
                m.job_sequencing = self.action_direct
        else:
            print("WARNING: ANN TYPE NOT SPECIFIED !!!!")

        print('--------------------------')
        #print("Dictionary of networks:\n",self.net_dict)
        # check if need to show the specific selection
        self.show = False
        if 'show' in kwargs and kwargs['show']:
            self.show = True

    def action_sqc_rule(self, local_data):
        s_t = self.build_state(local_data)
        value = self.network.forward(s_t.reshape([1,1,self.input_size]))
        a_t = torch.argmax(value)
        job_position = self.func_list[a_t](local_data)
        return job_position

    def action_direct(self, sqc_data): # strategic idleness is prohibitted
        s_t = self.build_state(sqc_data)
        m_idx = sqc_data[-1]
        value = self.network.forward(s_t.reshape([1]+self.input_size_as_list),m_idx).squeeze()
        a_t = torch.argmax(value)
        job_position, j_idx = self.action_conversion(a_t)
        return job_position

    def check_parameter(self):
        print('------------------ Sequencing Brain Parameter Check ------------------')
        print("Collect from:",self.address_seed)
        print('Trained with Rwd.Func.:',self.kwargs['reward_function'])
        print('State function:',self.build_state.__name__)
        print('ANN architecture:',self.network.__class__.__name__)
        print('*** SCENARIO:')
        print("Configuration: {} work centers, {} machines".format(len(self.job_creator.wc_list),len(self.m_list)))
        print("PT heterogeneity:",self.job_creator.pt_range)
        print('Due date tightness:',self.job_creator.tightness)
        print('Utilization rate:',self.job_creator.E_utliz)
        print('----------------------------------------------------------------------')
