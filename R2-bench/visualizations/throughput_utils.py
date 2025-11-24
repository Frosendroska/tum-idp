"""
Shared utilities for throughput calculations with prorating across phases and time windows.
"""

import pandas as pd
import logging

logger = logging.getLogger(__name__)


def get_phase_boundaries(data: pd.DataFrame) -> dict:
    """
    Extract phase boundaries from data based on when requests started in each phase.
    
    For each phase, the boundary is defined as:
    - phase_start: minimum start_ts of requests that started in this phase
    - phase_end: maximum end_ts of requests that started in this phase
    
    Returns a dictionary mapping phase_id to (start_time, end_time) tuples.
    """
    if len(data) == 0:
        return {}
    
    phase_boundaries = {}
    
    for phase_id in data['phase_id'].unique():
        # Get all requests that STARTED in this phase
        phase_data = data[data['phase_id'] == phase_id]
        if 'start_ts' not in phase_data.columns or 'end_ts' not in phase_data.columns:
            logger.warning(f"Phase {phase_id} missing start_ts/end_ts, skipping")
            continue
        # Phase starts when first request in this phase starts
        phase_start = phase_data['start_ts'].min()
        # Phase ends when last request that started in this phase ends
        phase_end = phase_data['end_ts'].max()
        phase_boundaries[phase_id] = (phase_start, phase_end)
    
    return phase_boundaries


def calculate_phase_throughput_with_prorating(
    data: pd.DataFrame,
    phase_id: str,
    phase_boundaries: dict = None
) -> dict:
    """
    Calculate throughput for a specific phase with proper prorating across phase boundaries.
    
    This function prorates bytes from ALL requests that overlap with the phase,
    based on the proportion of time each request spent in that phase.
    
    Args:
        data: DataFrame with request data (must have start_ts, end_ts, bytes, phase_id)
        phase_id: Phase ID to calculate for
        phase_boundaries: Optional pre-computed phase boundaries dict
    
    Returns:
        Dictionary with phase statistics including prorated throughput
    """
    # Filter to successful requests
    successful_data = data[data.get('http_status', 200) == 200].copy()
    
    if len(successful_data) == 0:
        return {
            'total_bytes': 0,
            'duration_seconds': 0,
            'throughput_mbps': 0,
            'request_count': 0,
            'phase_start': 0,
            'phase_end': 0
        }
    
    # Get phase boundaries if not provided
    if phase_boundaries is None:
        phase_boundaries = get_phase_boundaries(data)
    
    if phase_id not in phase_boundaries:
        logger.warning(f"Phase {phase_id} not found in phase boundaries")
        return {
            'total_bytes': 0,
            'duration_seconds': 0,
            'throughput_mbps': 0,
            'request_count': 0,
            'phase_start': 0,
            'phase_end': 0
        }
    
    phase_start, phase_end = phase_boundaries[phase_id]
    phase_duration = phase_end - phase_start
    
    if phase_duration <= 0:
        return {
            'total_bytes': 0,
            'duration_seconds': 0,
            'throughput_mbps': 0,
            'request_count': 0,
            'phase_start': phase_start,
            'phase_end': phase_end
        }
    
    # Prorate all requests that overlap with this phase
    total_bytes = 0.0
    request_count = 0
    
    for _, request in successful_data.iterrows():
        request_start = request['start_ts']
        request_end = request['end_ts']
        request_bytes = request['bytes']
        
        # Check if request overlaps with this phase
        if request_start < phase_end and request_end > phase_start:
            # Calculate overlap
            overlap_start = max(request_start, phase_start)
            overlap_end = min(request_end, phase_end)
            overlap_duration = max(0, overlap_end - overlap_start)
            
            # Calculate total request duration
            request_duration = request_end - request_start
            
            if request_duration > 0:
                # Prorate bytes based on overlap
                prorated_bytes = (request_bytes * overlap_duration) / request_duration
                total_bytes += prorated_bytes
                request_count += 1
    
    # Calculate throughput
    throughput_mbps = (total_bytes * 8) / (phase_duration * 1_000_000) if phase_duration > 0 else 0
    
    return {
        'total_bytes': total_bytes,
        'duration_seconds': phase_duration,
        'throughput_mbps': throughput_mbps,
        'request_count': request_count,
        'phase_start': phase_start,
        'phase_end': phase_end
    }


def prorate_bytes_to_time_windows(
    data: pd.DataFrame,
    window_start_times: list,
    window_size_seconds: float = 1.0,
    start_col: str = 'start_ts',
    end_col: str = 'end_ts',
    bytes_col: str = 'bytes'
) -> pd.DataFrame:
    """
    Prorate bytes from requests across time windows based on actual request duration.
    
    This function handles requests that span multiple time windows by prorating
    the bytes proportionally based on how much of the request duration overlaps
    with each window.
    
    Args:
        data: DataFrame with request data, must have start_ts, end_ts, and bytes columns
        window_start_times: List of window start times (in seconds since epoch)
        window_size_seconds: Size of each time window in seconds (default: 1.0 for per-second)
        start_col: Column name for request start time (default: 'start_ts')
        end_col: Column name for request end time (default: 'end_ts')
        bytes_col: Column name for bytes transferred (default: 'bytes')
    
    Returns:
        DataFrame with columns: window_start, throughput_mbps, total_bytes, request_count, phase_id
    """
    if len(data) == 0:
        return pd.DataFrame(columns=['window_start', 'throughput_mbps', 'total_bytes', 'request_count', 'phase_id'])
    
    # Filter to successful requests only
    successful_data = data[data.get('http_status', 200) == 200].copy()
    
    if len(successful_data) == 0:
        return pd.DataFrame(columns=['window_start', 'throughput_mbps', 'total_bytes', 'request_count', 'phase_id'])
    
    # Ensure we have the required columns
    required_cols = [start_col, end_col, bytes_col]
    missing_cols = [col for col in required_cols if col not in successful_data.columns]
    if missing_cols:
        logger.error(f"Missing required columns: {missing_cols}. start_ts and end_ts are required.")
        return pd.DataFrame(columns=['window_start', 'throughput_mbps', 'total_bytes', 'request_count', 'phase_id'])
    
    # Get phase boundaries for determining which phase each window belongs to
    phase_boundaries = get_phase_boundaries(data)
    
    results = []
    
    for window_start in window_start_times:
        window_end = window_start + window_size_seconds
        
        # Find all requests that overlap with this window
        overlapping = successful_data[
            (successful_data[start_col] < window_end) & 
            (successful_data[end_col] > window_start)
        ]
        
        if len(overlapping) == 0:
            continue
        
        total_bytes = 0.0
        request_count = 0
        
        for _, request in overlapping.iterrows():
            request_start = request[start_col]
            request_end = request[end_col]
            request_bytes = request[bytes_col]
            
            # Calculate overlap between request and window
            overlap_start = max(request_start, window_start)
            overlap_end = min(request_end, window_end)
            overlap_duration = max(0, overlap_end - overlap_start)
            
            # Calculate total request duration
            request_duration = request_end - request_start
            
            if request_duration > 0:
                # Prorate bytes based on overlap
                prorated_bytes = (request_bytes * overlap_duration) / request_duration
                total_bytes += prorated_bytes
                request_count += 1
        
        # Calculate throughput in Mbps for this window
        throughput_mbps = (total_bytes * 8) / (window_size_seconds * 1_000_000)
        
        # Determine which phase this window belongs to based on phase boundaries
        # Use the phase that contains the majority of this window
        window_center = window_start + window_size_seconds / 2
        phase_id = None
        for pid, (p_start, p_end) in phase_boundaries.items():
            if p_start <= window_center <= p_end:
                phase_id = pid
                break
        
        # Fallback: use the most common phase_id from overlapping requests
        if phase_id is None and len(overlapping) > 0:
            phase_id = overlapping['phase_id'].mode()[0] if len(overlapping['phase_id'].mode()) > 0 else overlapping['phase_id'].iloc[0]
        
        results.append({
            'window_start': pd.to_datetime(window_start, unit='s'),
            'window_start_ts': window_start,
            'throughput_mbps': throughput_mbps,
            'total_bytes': total_bytes,
            'request_count': request_count,
            'phase_id': phase_id
        })
    
    if not results:
        return pd.DataFrame(columns=['window_start', 'throughput_mbps', 'total_bytes', 'request_count', 'phase_id'])
    
    return pd.DataFrame(results)
