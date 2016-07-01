from src.core.scripts import Script
from src.core import Parameter
from src.instruments import DAQ, B26PulseBlaster
import itertools
from copy import deepcopy
import time

from PySide.QtCore import Signal, QThread
from src.plotting.plots_1d import plot_delay_counts, plot_pulses, update_pulse_plot, update_delay_counts
import numpy as np

MAX_AVERAGES_PER_SCAN = 1000000  #1E6, the max number of loops per point allowed at one time (true max is ~4E6 since
                                 #pulseblaster stores this value in 22 bits in its register


class ExecutePulseBlasterSequence(Script, QThread):
    '''
This class is a base class that should be inherited by all classes that utilize the pulseblaster for experiments. The
_function part of this class takes care of high-level interaction with the pulseblaster for experiment control and optionally
the daq for reading counter input (usually from the APD). It also provides all of the functionality needed to run a
standard Script such as plotting.
To use this class, the inheriting class need only overwrite _create_pulse_sequences to create the proper pulse sequence
for a given experiment
    '''
    _DEFAULT_SETTINGS = Parameter(None)

    _INSTRUMENTS = {'daq': DAQ, 'PB': B26PulseBlaster}

    _SCRIPTS = {}
    updateProgress = Signal(int)

    def __init__(self, instruments, scripts=None, name=None, settings=None, log_function=None, data_path=None):
        """
        Standard script initialization
        Args:
            name (optional): name of script, if empty same as class name
            settings (optional): settings for this script, if empty same as default settings
        """
        Script.__init__(self, name, settings=settings, scripts=scripts, instruments=instruments,
                        log_function=log_function, data_path=data_path)
        QThread.__init__(self)

    def _function(self):
        '''
        This is the core loop in which the desired experiment specified by the inheriting script's pulse sequence
        is performed.

        Poststate: self.data contains two key/value pairs, 'tau' and 'counts'
            'tau': a list of the times tau that are scanned over for the relative experiment (ex wait times between pulses)
             'counts': the counts received from the experiment. This is a len('tau') list, with each element being a list
             of length 1, 2, or 3 corresponding to the sum over all trials for a single tau time. In this sublist, the
             first value is the signal, the second (optional) value is counts in the |0> state (the maximum counts for
             normalization), and the third (optional) value is the counts in the |1> state (the minimum counts for
             normalization)

        '''
        self.pulse_sequences, self.num_averages, tau_list, self.measurement_gate_width = self._create_pulse_sequences()

        #calculates the number of daq reads per loop requested in the pulse sequence by asking how many apd reads are
        #called for. if this is not calculated properly, daq will either end too early (number too low) or hang since it
        #never receives the rest of the counts (number too high)
        num_daq_reads = 0
        for pulse in self.pulse_sequences[0]:
            if pulse.channel_id == 'apd_readout':
                num_daq_reads += 1

        signal = [0]
        norms = np.repeat([1], (num_daq_reads - 1))
        self.count_data = np.repeat([np.append(signal, norms)], len(self.pulse_sequences), axis=0)

        self.data = {'tau': tau_list, 'counts': deepcopy(self.count_data)}

        #divides the total number of averages requested into a number of slices of MAX_AVERAGES_PER_SCAN and a remainer.
        #This is required because the pulseblaster won't accept more than ~4E6 loops (22 bits avaliable to store loop
        #number) so need to break it up into smaller chunks (use 1E6 so initial results display faster)
        (num_1E6_avg_pb_programs, remainder) = divmod(self.num_averages, MAX_AVERAGES_PER_SCAN)

        for average_loop in range(int(num_1E6_avg_pb_programs)):
            if self._abort:
                break
            print('loop ' + str(average_loop))
            self._run_sweep(self.pulse_sequences, MAX_AVERAGES_PER_SCAN, num_daq_reads)

        if remainder != 0:
            self._run_sweep(self.pulse_sequences, remainder, num_daq_reads)

        if self.settings['save']:
            self.save_b26()
            self.save_data()
            self.save_log()
            self.save_image_to_disk()

        self.updateProgress.emit(100)

    def _plot(self, axes_list):
        '''
        Plot 1: self.data['tau'], the list of times specified for a given experiment, verses self.data['counts'], the data
        received for each time
        Plot 2: the pulse sequence performed at the current time (or if plotted statically, the last pulse sequence
        performed

        Args:
            axes_list: list of axes to write plots to (uses first 2)

        '''
        counts = self.data['counts']
        x_data = self.data['tau']
        axis1 = axes_list[0]
        if not counts == []:
            plot_delay_counts(axis1, x_data, counts)
        axis2 = axes_list[1]
        plot_pulses(axis2, self.pulse_sequences[self.sequence_index])

    def _update_plot(self, axes_list):
        '''
        Updates plots specified in _plot above
        Args:
            axes_list: list of axes to write plots to (uses first 2)

        '''
        counts = self.data['counts']
        x_data = self.data['tau']
        axis1 = axes_list[0]
        if not counts == []:
            update_delay_counts(axis1, x_data, counts)
        axis2 = axes_list[1]
        update_pulse_plot(axis2, self.pulse_sequences[self.sequence_index])

    def _run_sweep(self, pulse_sequences, num_loops_sweep, num_daq_reads):
        '''
        Each pulse sequence specified in pulse_sequences is run num_loops_sweep consecutive times.

        Args:
            pulse_sequences: a list of pulse sequences to run, each corresponding to a different value of tau. Each
                             sequence is a list of Pulse objects specifying a given pulse sequence
            num_loops_sweep: number of times to repeat each sequence before moving on to the next one
            num_daq_reads: number of times the daq must read for each sequence (generally 1, 2, or 3)

        Poststate: self.data['counts'] is updated with the acquired data

        '''
        for index, sequence in enumerate(pulse_sequences):
            if self._abort:
                break
            result = self._single_sequence(sequence, num_loops_sweep, num_daq_reads)  # keep entire array
            self.count_data[index] = self.count_data[index] + result
            self.data['counts'][index] = self._normalize_to_kCounts(self.count_data[index], self.measurement_gate_width,
                                                                    self.num_averages)  # make function
            self.sequence_index = index
            # self.updateProgress.emit(int(99 * (index + 1.0) / len(self.pulse_sequences) / num_1E6_avg_pb_programs + (99 * (average_loop / num_1E6_avg_pb_programs))))
            self.updateProgress.emit(self._calc_progress())

    def _single_sequence(self, pulse_sequence, num_loops, num_daq_reads):
        '''
        Runs a single pulse sequence, num_loops consecutive times
        Args:
            pulse_sequence: a list of Pulse objects specifying a pulse sequence
            num_loops: number of times to repeat the pulse sequence
            num_daq_reads: number of times sequence requires that the

        Returns: a list containing, 1, 2, or 3 values depending on the pulse sequence
        counts, the second is the number of

        '''
        self.instruments['PB']['instance'].program_pb(pulse_sequence,
                                                      num_loops=num_loops)
        timeout = 2 * self.instruments['PB']['instance'].estimated_runtime
        if num_daq_reads != 0:
            self.instruments['daq']['instance'].gated_DI_init('ctr0', int(num_loops * num_daq_reads))
            self.instruments['daq']['instance'].gated_DI_run()
        self.instruments['PB']['instance'].start_pulse_seq()
        if num_daq_reads != 0:
            result_array, _ = self.instruments['daq']['instance'].gated_DI_read(
                timeout=timeout)  # thread waits on DAQ getting the right number of gates
            for i in range(num_daq_reads):
                result = sum(itertools.islice(result_array, i, None, num_daq_reads))
        # clean up APD tasks
        if num_daq_reads != 0:
            self.instruments['daq']['instance'].gated_DI_stop()

        return result

    # MUST BE IMPLEMENTED IN INHERITING SCRIPT
    def _create_pulse_sequences(self):
        '''
        A function to create the pulse sequence. This must be overwritten in scripts inheriting from this script

        Returns: pulse_sequences, num_averages, tau_list
            pulse_sequences: a list of pulse sequences, each corresponding to a different time 'tau' that is to be
            scanned over. Each pulse sequence is a list of pulse objects containing the desired pulses. Each pulse
            sequence must have the same number of daq read pulses
            num_averages: the number of times to repeat each pulse sequence
            tau_list: the list of times tau, with each value corresponding to a pulse sequence in pulse_sequences


        '''
        raise NotImplementedError

    def _calc_progress(self):

        self.updateProgress.emit(50)

    def _normalize(self, signal, baseline_max=0, baseline_min=0):
        '''
        Normalizes the signal values given a maximum value (counts in |0>) and optionally minimum value (counts in |1>,
        set to 0 if none provided). If no maximum given, returns the bare signal.
        Args:
            signal:
            baseline_max:
            baseline_min:

        Returns:

        '''
        if baseline_max == 0:
            return signal
        else:
            return ((signal - baseline_min) / (baseline_max - baseline_min))

    def _normalize_to_kCounts(self, signal, gate_width=1, num_averages=1):
        return (signal * (10E9 / (gate_width * num_averages)))

    def validate(self):
        self.pulse_sequences_preview = self._create_pulse_sequences()
        failure_list = []
        for sequence_index, pulse_sequence in enumerate(self.pulse_sequences_preview[0]):
            for pulse_index, pulse in enumerate(pulse_sequence):
                print(pulse.duration)
                if pulse.duration < 15:
                    print('FAILURE', sequence_index, pulse_index)

    def _plot_validate(self, axes_list):
        axis1 = axes_list[0]
        axis2 = axes_list[1]
        plot_pulses(axis2, self.pulse_sequences_preview[0][0])
        plot_pulses(axis1, self.pulse_sequences_preview[0][-1])



if __name__ == '__main__':
    script = {}
    instr = {}
    script, failed, instr = Script.load_and_append({'ExecutePulseBlasterSequence': 'ExecutePulseBlasterSequence'},
                                                   script, instr)

    print(script)
    print(failed)
    print(instr)
