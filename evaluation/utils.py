import atexit
import signal
import multiprocessing.pool
import threading
from contextlib import contextmanager

import tqdm

import evaluation.models.models

def replace_model_name_slashes(model_name: str) -> str:
    """
    The model name can be something like OpenAssistant/oasst-sft-1-pythia-12b.
    The path where we store evaluation results should depend on the model name,
    but paths can't include '/', so we need to replace that.
    """

    return model_name.replace('/', '--')

def undo_replace_model_name_slashes(model_name: str) -> str:
    return model_name.replace('--', '/')

@contextmanager
def changed_exit_handlers():
    previous_sigterm = signal.getsignal(signal.SIGTERM)
    previous_sigint = signal.getsignal(signal.SIGINT)

    atexit.register(evaluation.models.models.unload_model)
    signal.signal(signal.SIGTERM, evaluation.models.models.unload_model)
    signal.signal(signal.SIGINT, evaluation.models.models.unload_model)

    yield

    atexit.unregister(evaluation.models.models.unload_model)
    signal.signal(signal.SIGTERM, previous_sigterm)
    signal.signal(signal.SIGINT, previous_sigint)

def process_with_thread_pool(*, num_threads, items, process_function, desc=None):
    def process_with_index(item_with_index):
        index, item = item_with_index
        result = process_function(item)
        return index, result

    with multiprocessing.pool.ThreadPool(min(num_threads, len(items))) as pool:
        iterator = pool.imap_unordered(process_with_index, enumerate(items))
        results_with_indices = list(tqdm.tqdm(iterator, total=len(items), desc=desc))

    return [result_with_index[1] for result_with_index in sorted(results_with_indices, key=lambda item: item[0])]

def join_threads():
    for thread in threading.enumerate():
        if thread.daemon:
            continue

        try:
            thread.join()
        except RuntimeError as error:
            if 'cannot join current thread' in error.args[0]: # main thread
                pass
            else:
                raise
