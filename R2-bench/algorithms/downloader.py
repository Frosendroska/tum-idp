"""
Simple downloader algorithm for the R2 benchmark.
"""

import logging
from ..persistence.base import BenchmarkRecord

logger = logging.getLogger(__name__)


class SimpleDownloader:
    """Simple algorithm for downloading data from object storage."""
    
    def __init__(self, storage_system, range_size_mb: int = 100):
        self.storage_system = storage_system
        self.range_size_mb = range_size_mb
        self.object_key = "test-object-1gb"
        
        logger.info(f"Initialized downloader with {range_size_mb}MB range size")
    
    def download_range(self, range_start: int, range_length: int):
        """Download a specific range from the object."""
        try:
            data, latency_ms = self.storage_system.download_range(
                self.object_key, range_start, range_length
            )
            
            if data and len(data) > 0:
                return {
                    'success': True,
                    'data': data,
                    'latency_ms': latency_ms,
                    'bytes_downloaded': len(data)
                }
            else:
                return {
                    'success': False,
                    'data': None,
                    'latency_ms': latency_ms,
                    'bytes_downloaded': 0
                }
                
        except Exception as e:
            logger.error(f"Failed to download range {range_start}-{range_start + range_length - 1}: {e}")
            return {
                'success': False,
                'data': None,
                'latency_ms': 0,
                'bytes_downloaded': 0,
                'error': str(e)
            }
    
    def download_whole_file(self):
        """Download the entire test object."""
        try:
            # For large files, we'll download in chunks
            chunk_size = self.range_size_mb * 1024 * 1024
            total_size = 1024 * 1024 * 1024  # 1GB
            
            chunks = []
            total_latency = 0
            
            for start in range(0, total_size, chunk_size):
                end = min(start + chunk_size, total_size)
                chunk_length = end - start
                
                result = self.download_range(start, chunk_length)
                if result['success']:
                    chunks.append(result['data'])
                    total_latency += result['latency_ms']
                else:
                    logger.error(f"Failed to download chunk starting at {start}")
                    return None
            
            # Combine chunks
            full_data = b''.join(chunks)
            
            return {
                'success': True,
                'data': full_data,
                'latency_ms': total_latency,
                'bytes_downloaded': len(full_data)
            }
            
        except Exception as e:
            logger.error(f"Failed to download whole file: {e}")
            return None
