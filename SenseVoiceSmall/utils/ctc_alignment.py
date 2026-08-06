
import torch
import numpy as np

def ctc_align(probs, labels, blank_id=0):
    """Simplified CTC alignment"""
    T = probs.shape[0] if hasattr(probs, 'shape') else len(probs)
    L = len(labels)
    
    alignment = []
    t, l = 0, 0
    
    while t < T and l < L:
        if hasattr(probs, 'shape'):
            token = torch.argmax(probs[t]).item()
        else:
            token = np.argmax(probs[t])
            
        if token == blank_id:
            alignment.append(blank_id)
            t += 1
        elif token == labels[l]:
            alignment.append(token)
            t += 1
            l += 1
        else:
            alignment.append(blank_id)
            t += 1
    
    while t < T:
        alignment.append(blank_id)
        t += 1
    
    return alignment

def compute_ctc_loss(log_probs, targets, input_lengths, target_lengths, blank=0):
    """Compute CTC loss"""
    return torch.nn.functional.ctc_loss(
        log_probs.transpose(0, 1),
        targets,
        input_lengths,
        target_lengths,
        blank=blank,
        zero_infinity=True
    )

__all__ = ['ctc_align', 'compute_ctc_loss']
