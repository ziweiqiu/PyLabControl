
import datetime
from PyQt4 import QtCore
from hardware_modules.instruments import Parameter, Instrument

class Script(object):
    def __init__(self, name = None, settings = []):
        '''
        generic script class
        :param name: name of script
        :param threading: if script is excecuted on thread, default is False
        '''
        if name is None:
            name = self.__class__.__name__
        self.name = name
        # set end time to be before start time if script hasn't been excecuted this tells us
        self.time_start = datetime.datetime.now()
        self.time_end =self.time_start - datetime.timedelta(seconds=1)

        self._settings = self.settings_default
        self.update_settings(settings)

    def __str__(self):
        pass
        #todo: finsish implementation
        # def parameter_to_string(parameter):
        #     # print('parameter', parameter)
        #     return_string = ''
        #     # if value is a list of parameters
        #     if isinstance(parameter.value, list) and isinstance(parameter.value[0],Parameter):
        #         return_string += '{:s}\n'.format(parameter.name)
        #         for element in parameter.value:
        #             return_string += parameter_to_string(element)
        #     elif isinstance(parameter, Parameter):
        #         return_string += '\t{:s}:\t {:s}\n'.format(parameter.name, str(parameter.value))
        #
        #     return return_string
        #
        output_string = '{:s} (class type: {:s})\n'.format(self.name, self.__class__.__name__)
        output_string += 'threading = {:s}'.format(str(self.threading))

        output_string += 'settings:\n'
        for element in self.settings:
            output_string += str(element)+'\n'
        return output_string
    @property
    def name(self):
        return self._name
    @name.setter
    def name(self, value):
        if isinstance(value, str):
            self._name = value
        else:
            raise TypeError('Name has to be a string')

    @property
    def settings_default(self):
        '''
        returns the default settings of the script
        settings contain Parameters, Instruments and Scripts
        :return:
        '''
        settings_default = []
        return settings_default

    @property
    def settings(self):
        '''
        :return: returns the settings of the script
        settings contain Parameters, Instruments and Scripts
        '''
        return self._settings

    def update_settings(self, settings_new):
        '''
        updates the settings if they exist
        :param settings_new:
        :return:
        '''

        def check_settings_list(settings):
            '''
            check if settings is a list of settings or a dictionary
            if it is a dictionary we create a settings list from it
            '''
            if isinstance(settings, dict):
                settings_new = []
                for key, value in settings.iteritems():
                    settings_new.append(Parameter(key, value))
            elif isinstance(settings, list):
                # if list element is not a  parameter, instrument or script cast it into a parameter
                settings_new = [element if isinstance(element, (Parameter, Instrument, Script)) else Parameter(element) for element in settings]
            else:
                raise TypeError('settings should be a valid list or dictionary!')
            return settings_new

        for setting in check_settings_list(settings_new):
            # get index of setting in default list
            index = [i for i, s in enumerate(self.settings_default) if s == setting]
            if len(index)>1:
                raise TypeError('Error: Dublicate setting in default list')
            elif len(index)==1:
                self.settings[index[0]].update(setting)

    @property
    def dict(self):
        '''
        returns the configuration of the script as a dictionary
        that contains {'parameters': parameters, 'instruments':instruments, 'scripts': scripts}
        :return: nested dictionary with entries name and value
        '''
        # build dictionary

        config = {}
        # todo: implement
        # for p in self._parameter_list:
        #     config.update(p.dict)

        return config

    @property
    def time_end(self):
        '''
        time when script execution started
        :return:
        '''
        return self._time_stop
    @time_end.setter
    def time_end(self, value):
        assert isinstance(value, datetime.datetime)
        self._time_stop = value

    @property
    def time_start(self):
        '''
        time when script execution started
        :return:
        '''
        return self._time_start
    @time_start.setter
    def time_start(self, value):
        assert isinstance(value, datetime.datetime)
        self._time_start = value

    @property
    def excecution_time(self):
        '''
        :return: script excecition time as time_delta object to get time in seconds use .total_seconds()
        '''
        return self.time_end - self.time_start

    def run(self):
        '''
        executes the script
        :return: boolean if execution of script finished succesfully
        '''
        self.is_running = True
        self.time_start  = datetime.datetime.now()
        while self.is_running and self.abort == False:
            # do something
            self.is_running = False

        self.time_end  = datetime.datetime.now()

        success = self.abort == False
        return success


        return success

class QtScript(QtCore.QThread, Script):
    '''
    This class starts a script on its own thread
    '''

    #You can do any extra things in this init you need
    def __init__(self, name = None, settings = []):
        """

        :param
        :return:
        """
        self._recording = False

        QtCore.QThread.__init__(self)
        Script.__init__(self, name, settings)

    def __del__(self):
        self.stop()

    #A QThread is run by calling it's start() function, which calls this run()
    #function in it's own "thread".
    def run(self):
        import time
        import random

        self.is_running = True
        self.time_start  = datetime.datetime.now()
        while self.is_running and self._abort == False:
            # do something
            self.updateProgress.emit(random.random())
            time.sleep(0.2)

        self.time_end  = datetime.datetime.now()

        success = self._abort == False
        return success

    def stop(self):
        self._abort = False



class QtScript_Dummy(QtScript):
    #This is the signal that will be emitted during the processing.
    #By including int as an argument, it lets the signal know to expect
    #an integer argument when emitting.
    updateProgress = QtCore.Signal(int)

    def __init__(self, name, threading, settings):
        super(QtScript_Dummy, self).__init__(name, settings)

    @property
    def settings_default(self):
        '''
        returns the default settings of the script
        settings contain Parameters, Instruments and Scripts
        :return:
        '''
        settings_default = [
            Parameter({'a':0}),
            Parameter({'b':0.1})
        ]
        return settings_default
    @property
    def a(self):
        return [element for element in self.settings if element.name == 'a'][0]

    #A QThread is run by calling it's start() function, which calls this run()
    #function in it's own "thread".
    def run(self):
        import time
        import random

        self.is_running = True
        self.time_start  = datetime.datetime.now()
        while self.is_running and self._abort == False:
            random.random()
            # do something
            self.updateProgress.emit()
            self.settings[]
            print('a' : signal)
            time.sleep(0.2)

        self.time_end  = datetime.datetime.now()

        success = self._abort == False
        return success

class Script_Dummy(Script):
    def __init__(self, name, settings):
        super(Script_Dummy, self).__init__(name, settings)
    @property
    def settings_default(self):
        '''
        returns the default settings of the script
        settings contain Parameters, Instruments and Scripts
        :return:
        '''
        settings_default = [
            Parameter({'a':0}),
            Parameter({'b':0.1})
        ]
        return settings_default


def testing():
    script = Script_Dummy('test script', False, {'a': 0, 'b':1.2})

    print(script)
    print(script.settings)


if __name__ == '__main__':

    pass


