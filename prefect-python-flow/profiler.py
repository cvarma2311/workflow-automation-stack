import functools
import time
import psutil
import os
from prefect import get_run_logger

def memory_profiler(func):
    """
    A decorator that profiles the memory and time usage of a function.
    It logs the results using the Prefect logger.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = get_run_logger()
        process = psutil.Process(os.getpid())

        # Log memory before execution
        mem_before_rss = process.memory_info().rss / (1024 * 1024)  # RSS in MB
        mem_before_vms = process.memory_info().vms / (1024 * 1024)  # VMS in MB
        logger.info(f"Starting '{func.__name__}'... | RAM: RSS={mem_before_rss:.2f} MB, VMS={mem_before_vms:.2f} MB")

        # Start timer and execute the function
        start_time = time.time()
        
        # Track peak memory during execution
        peak_mem_rss = mem_before_rss
        peak_mem_vms = mem_before_vms

        # The actual function execution
        result = func(*args, **kwargs)
        
        end_time = time.time()

        # Get memory after execution
        mem_after_rss = process.memory_info().rss / (1024 * 1024)  # RSS in MB
        mem_after_vms = process.memory_info().vms / (1024 * 1024)  # VMS in MB
        
        # Check for peak memory during this period (could be higher than after)
        peak_mem_rss = max(peak_mem_rss, process.memory_info().rss / (1024 * 1024))
        peak_mem_vms = max(peak_mem_vms, process.memory_info().vms / (1024 * 1024))

        duration = end_time - start_time

        logger.info(f"Finished '{func.__name__}'. | Duration: {duration:.2f} seconds")
        logger.info(f"RAM after '{func.__name__}': RSS={mem_after_rss:.2f} MB (Change: {mem_after_rss - mem_before_rss:+.2f} MB), VMS={mem_after_vms:.2f} MB (Change: {mem_after_vms - mem_before_vms:+.2f} MB)")
        logger.info(f"Peak RAM during '{func.__name__}': RSS={peak_mem_rss:.2f} MB, VMS={peak_mem_vms:.2f} MB")

        # Note: This profiler measures the memory of the Python process.
        # This provides an overall view of the resources consumed by the task,
        # but does not offer granular per-line memory usage of the Python code.

        return result
    return wrapper
