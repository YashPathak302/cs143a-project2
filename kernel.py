### Fill in the following information before submitting
# Group id: 45
# Members: Yash Pathak, Lawrence Tep, Caleb Yang

from collections import deque

# PID is just an integer, but it is used to make it clear when a integer is expected to be a valid PID.
PID = int

# This class represents the PCB of processes.
# It is only here for your convinience and can be modified however you see fit.
class PCB:
    pid: PID
    # Priority is also just an integer, but it is used to make it clear when a integer is expected to be a valid priority.
    priority: int
    process_type: str
    
    def __init__(self, pid: PID, priority: int = 32, process_type: str = "Foreground"):
        self.pid = pid
        self.priority = priority
        self.process_type = process_type

# This class represents the Kernel of the simulation.
# The simulator will create an instance of this object and use it to respond to syscalls and interrupts.
# DO NOT modify the name of this class or remove it.
class Kernel:
    scheduling_algorithm: str
    ready_queue: deque[PCB]
    waiting_queue: deque[PCB]
    running: PCB
    idle_pcb: PCB
    foreground_queue: deque[PCB]
    background_queue: deque[PCB]
    prev_pid: PID
    # Called before the simulation begins.
    # Use this method to initilize any variables you need throughout the simulation.
    # DO NOT rename or delete this method. DO NOT change its arguments.
    def __init__(self, scheduling_algorithm: str, logger):
        self.scheduling_algorithm = scheduling_algorithm
        self.ready_queue = deque()
        self.waiting_queue = deque()
        self.idle_pcb = PCB(0)
        self.running = self.idle_pcb
        # Dictionary to keep track of all processes by PID
        self.processes = {0: self.idle_pcb}
        self.logger = logger
        self.prev_pid = self.idle_pcb
        # stores semaphore_id mapped to its value and processes
        self.semaphores = {}  # {semaphore_id: {"value": int, "queue": deque[PCB]}}

        # stores mutex_id mapped to whether it's locked, its owner, and its processes
        self.mutexes = {} # {mutex_id: {"locked": bool, "owner": PID, "queue": deque[PCB]}}


        # for Round Robin scheduling, use a time quantum of 40 microseconds
        self.time_quantum = 40  # microseconds
        self.time_slice_remaining = self.time_quantum
        self.temp_time = 0
        
        # for multilevel 
        self.foreground_queue = deque()  # For RR scheduling
        self.background_queue = deque()  # For FCFS scheduling
        self.foreground_time_slice = 40  # RR time slice

        self.current_level = "Foreground"
        self.level_time_elapsed = 0
        self.level_switch_interval = 200  # microseconds
        self.relapse_flag = False

    # This method is triggered every time a new process has arrived.
    # new_process is this process's PID.
    # priority is the priority of new_process.
    # DO NOT rename or delete this method. DO NOT change its arguments.
    def new_process_arrived(self, new_process: PID, priority: int, process_type: str) -> PID:
        # Track the process type and priority
        # Update pcb with new process and priority
        # If the new process has a higher priority than the current running process, it should be added to the front of the queue.
        self.logger.log(f"Ready queue len:{len(self.ready_queue)} when process {new_process} arrived")
        new_pcb = PCB(new_process, priority, process_type)
        self.ready_queue.append(new_pcb)
        
        #check if new process is foreground or background
        if self.scheduling_algorithm == "Multilevel":
            if new_pcb.process_type == "Foreground":
                self.logger.log(f"Placing in foreground queue: {new_process}")
                self.foreground_queue.append(new_pcb)
            else: 
                self.logger.log(f"Placing in background queue: {new_process}")
                self.background_queue.append(new_pcb)
                
        
        # for bookkeeping (optional)
        # self.processes[new_process] = new_pcb
        
        # Optional line: to track the process type and priority after adding to the ready queue
        # self.logger.log(f"Process {new_process} with priority {priority} added to the ready queue")
        
        # Decide whether to preempt the current process or not.
        # If the current process is idle, we should always preempt it.
        # If the scheduling algorithm is FCFS, we should not preempt it.
        # If the scheduling algorithm is Priority, we should preempt it if the new process has a higher priority than the current process.
        if self.running == self.idle_pcb:
            # Always preempt the idle process
            self.running = self.choose_next_process()
            self.current_level = self.running.process_type
            self.level_time_elapsed = 0
            # For Round Robin scheduling, we need to reset the time slice for the new process
            self.time_slice_remaining = self.time_quantum
        
        elif self.scheduling_algorithm == "Priority" and self.is_higher_priority(new_pcb, self.running):
            # Put the current running process back in the queue
            self.ready_queue.append(self.running)
            # Choose the next process to run (which should be the higher priority one)
            self.running = self.choose_next_process()
            # For Round Robin scheduling, we need to reset the time slice for the new process
            self.time_slice_remaining = self.time_quantum
        
        elif self.scheduling_algorithm == "RR":
            # No priority, just Round Robin — new process joins queue, continue current
            pass

        return self.running.pid if self.running is not None else None
    
    
    # Helper function to check if a process has a higher priority than another process.
    def is_higher_priority(self, new_process: PCB, current_process: PCB) -> bool:
        # Higher priority is represented by a lower number.
        # In case of a tie, the process with the lower PID gets priority
        if new_process.priority < current_process.priority:
            return True
        elif new_process.priority == current_process.priority and new_process.pid < current_process.pid:
            return True
        return False

    # This method is triggered every time the current process performs an exit syscall.
    # DO NOT rename or delete this method. DO NOT change its arguments.
    def syscall_exit(self) -> PID:
        self.running = self.choose_next_process()
        # For round robin scheduling, we need to reset the time slice for the new process
        
        if self.scheduling_algorithm != "Multilevel":
            self.time_slice_remaining = self.time_quantum
        return self.running.pid

    # This method is triggered when the currently running process requests to change its priority.
    # DO NOT rename or delete this method. DO NOT change its arguments.
    def syscall_set_priority(self, new_priority: int) -> PID:
        # Update the priority of the running process
        self.running.priority = new_priority
        
        # For Priority scheduling, we need to check if we should preempt
        if self.scheduling_algorithm == "Priority":
            # Save the current running process
            current = self.running
            
            # See if there's a higher priority process in the ready queue
            highest_priority = None
            for process in self.ready_queue:
                if highest_priority is None or self.is_higher_priority(process, highest_priority):
                    highest_priority = process
            
            # If there's a process with higher priority, preempt
            if highest_priority and self.is_higher_priority(highest_priority, current):
                self.ready_queue.remove(highest_priority)
                self.ready_queue.append(current)
                self.running = highest_priority
        
        return self.running.pid


    # This is where you can select the next process to run.
    # This method is not directly called by the simulator and is purely for your convinience.
    # Feel free to modify this method as you see fit.
    # It is not required to actually use this method but it is recommended.
    def choose_next_process(self):
        self.logger.log(f"Choosing next process")
        if self.scheduling_algorithm != "Multilevel":
            if not self.ready_queue:
                return self.idle_pcb
        else:
            if not self.foreground_queue and not self.background_queue:
                return self.idle_pcb
        
        if self.scheduling_algorithm == "FCFS":
            return self.ready_queue.popleft()
        
        elif self.scheduling_algorithm == "Priority":
            # Find the process with the highest priority (lowest priority number)
            highest_priority_process = None
            
            for process in self.ready_queue:
                if highest_priority_process is None or self.is_higher_priority(process, highest_priority_process):
                    highest_priority_process = process
            
            # Remove it from the ready queue and return it
            if highest_priority_process:
                self.ready_queue.remove(highest_priority_process)
                return highest_priority_process
            
            return self.idle_pcb
        
        elif self.scheduling_algorithm == "RR":
            # Round Robin: FIFO order
            self.time_slice_remaining = self.time_quantum
            return self.ready_queue.popleft()
        
        elif self.scheduling_algorithm == "Multilevel":
            if self.current_level == "Foreground": # Foreground
                if self.foreground_queue:
                    self.time_slice_remaining = self.time_quantum
                    temp = self.foreground_queue.popleft()
                else:
                    self.current_level = "Background"
                    self.level_time_elapsed = 0
                    self.logger.log("Switching from foreground to background")
                    temp = self.background_queue.popleft()
                    
                self.logger.log(f"Foreground popping {temp.pid}")
                return temp
            else: # Background
                if self.background_queue:
                    temp = self.background_queue.popleft()
                else:
                    self.current_level = "Foreground"
                    self.level_time_elapsed = 0
                    self.logger.log("Switching from background to foreground")
                    temp = self.foreground_queue.popleft()
                    
                    
                self.logger.log(f"Background popping {temp.pid}")
                self.logger.log(f"{self.time_slice_remaining}")
                return temp
        
        # Default fallback
        return self.idle_pcb
    
    
    # This method is triggered when the currently running process requests to initialize a new semaphore.
    # DO NOT rename or delete this method. DO NOT change its arguments.
    def syscall_init_semaphore(self, semaphore_id: int, initial_value: int):
        self.semaphores[semaphore_id] = {
            "value": initial_value,
            "queue": deque()
        }

    # This method is triggered when the currently running process calls p() on an existing semaphore.
	# DO NOT rename or delete this method. DO NOT change its arguments.
    def syscall_semaphore_p(self, semaphore_id: int) -> PID:
        sem = self.semaphores[semaphore_id]
        sem["value"] -= 1

        if sem["value"] < 0: # block
            sem["queue"].append(self.running)
            self.running = self.choose_next_process()
            return self.running.pid

        # Continue running current process
        return self.running.pid


    # This method is triggered when the currently running process calls v() on an existing semaphore.
	# DO NOT rename or delete this method. DO NOT change its arguments.
    def syscall_semaphore_v(self, semaphore_id: int) -> PID:
        sem = self.semaphores[semaphore_id]
        sem["value"] += 1

        if sem["value"] <= 0 and sem["queue"]:
            if self.scheduling_algorithm == "FCFS" or self.scheduling_algorithm == "RR":
                unblocked = min(sem["queue"], key = lambda p: p.pid)
            elif self.scheduling_algorithm == "Priority":
                unblocked = min(sem["queue"], key = lambda p: (p.priority, p.pid))

            sem["queue"].remove(unblocked)

            if self.scheduling_algorithm == "Priority" and unblocked:
                if unblocked.priority < self.running.priority:
                    self.ready_queue.append(self.running)
                    self.running = unblocked
                    return self.running.pid

            self.ready_queue.append(unblocked)

        return self.running.pid


    # This method is triggered when the currently running process requests to initialize a new mutex.
	# DO NOT rename or delete this method. DO NOT change its arguments.
    def syscall_init_mutex(self, mutex_id: int):
        self.mutexes[mutex_id] = {
            "locked": False,
            "owner": None,
            "queue": deque()
        }


    # This method is triggered when the currently running process calls lock() on an existing mutex.
	# DO NOT rename or delete this method. DO NOT change its arguments.
    def syscall_mutex_lock(self, mutex_id: int) -> PID:
        mutex = self.mutexes[mutex_id]

        if not mutex["locked"]: # This mutex is available
            mutex["locked"] = True
            mutex["owner"] = self.running.pid
            return self.running.pid

        # Otherwise, block the current process
        mutex["queue"].append(self.running)
        self.running = self.choose_next_process()
        return self.running.pid


    # This method is triggered when the currently running process calls unlock() on an existing mutex.
	# DO NOT rename or delete this method. DO NOT change its arguments.
    def syscall_mutex_unlock(self, mutex_id: int) -> PID:
        mutex = self.mutexes[mutex_id]

        if mutex["owner"] != self.running.pid:
            return self.running.pid  # silently ignore

        mutex["locked"] = False
        mutex["owner"] = None

        if mutex["queue"]:  # If any processes are waiting
            if self.scheduling_algorithm in ["FCFS", "RR"]:
                next_process = min(mutex["queue"], key = lambda p: p.pid)
            elif self.scheduling_algorithm == "Priority":
                next_process = min(mutex["queue"], key = lambda p: (p.priority, p.pid))

            mutex["queue"].remove(next_process)

            # Give mutex to next process
            mutex["locked"] = True
            mutex["owner"] = next_process.pid

            if self.scheduling_algorithm == "Priority" and next_process.priority < self.running.priority:
                self.ready_queue.append(self.running)
                self.running = next_process
                return self.running.pid

            self.ready_queue.append(next_process)

        return self.running.pid

    # This function represents the hardware timer interrupt.
	# It is triggered every 10 microseconds and is the only way a kernel can track passing time.
    # Do not use real time to track how much time has passed as time is simulated.
	# DO NOT rename or delete this method. DO NOT change its arguments.
    def timer_interrupt(self) -> PID:
        if self.scheduling_algorithm == "Multilevel":
            self.level_time_elapsed += 10
            self.logger.log(f"[TIMER] Level: {self.current_level}, Running: {self.running.pid}")
            self.logger.log(f"Time slice remaining: {self.time_slice_remaining}")
            if self.current_level == "Foreground":
                self.time_slice_remaining -= 10
                
                if self.time_slice_remaining <= 0:
                # Enqueue current to end and rotate RR
                    self.logger.log(f"PID {self.running.pid} out of time slice")
                    self.time_slice_remaining = self.time_quantum
                    if self.prev_pid == self.running.pid:
                        self.relapse_flag = True
                    else:
                        self.relapse_flag = False
                    if self.level_time_elapsed >= self.level_switch_interval:
                        self.foreground_queue.append(self.running)
                        self.prev_pid = self.running.pid
                        self.running = self.choose_next_process()
                    else:
                        self.prev_pid = self.running.pid
                        self.foreground_queue.append(self.running) 
                        self.running = self.choose_next_process()
                    
            
            # after 200, switch
            if self.level_time_elapsed >= self.level_switch_interval:
                if self.relapse_flag == True:
                    self.logger.log("Using relapse flag")
                    self.temp_time = self.time_quantum
                    self.relapse_flag = False
                else:
                    self.logger.log("Using remaining time")
                    self.temp_time = self.time_slice_remaining
                if self.current_level == "Foreground" and self.background_queue:
                    self.logger.log(f"Switching to background queue from foreground")
                    self.foreground_queue.appendleft(self.running)
                    self.current_level = "Background"
                    self.level_time_elapsed = 0
                    self.running = self.choose_next_process()
                elif self.current_level == "Background" and self.foreground_queue:
                    self.logger.log(f"Switching to foreground queue from background")
                    self.background_queue.appendleft(self.running)
                    self.current_level = "Foreground"
                    self.level_time_elapsed = 0
                    
                    self.running = self.choose_next_process()
                    self.time_slice_remaining = self.temp_time
                else:
                    self.logger.log(f"Remaining in queue")
                    self.level_time_elapsed = 0
                    
            return self.running.pid
                
        else:
            if self.running == self.idle_pcb:
                return self.running.pid
                
            # Deduct 10μs from the current process's quantum
            if self.scheduling_algorithm == "RR":
                self.time_slice_remaining -= 10

                # If the process still has time, it continues running
                if self.time_slice_remaining > 0:
                    return self.running.pid

                # Otherwise, time quantum expired — preempt and switch
                self.logger.log("Time quantum")
                self.ready_queue.append(self.running)
                
                
                # Choose the next process
                self.running = self.choose_next_process()

                # Reset the time slice for the new running process
                self.time_slice_remaining = self.time_quantum

            return self.running.pid