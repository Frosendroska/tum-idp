package storage

import (
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"

	"github.com/xitongsys/parquet-go-source/local"
	"github.com/xitongsys/parquet-go/writer"
	"r2-bench"
)

// ParquetWriter handles writing benchmark results to Parquet files
type ParquetWriter struct {
	writer    *writer.ParquetWriter
	file      *local.LocalFile
	mutex     sync.Mutex
	filePath  string
	batchSize int
	results   []main.RequestResult
}

// NewParquetWriter creates a new Parquet writer
func NewParquetWriter(outputDir string, batchSize int) (*ParquetWriter, error) {
	if err := os.MkdirAll(outputDir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create output directory: %w", err)
	}

	timestamp := time.Now().Format("20060102-150405")
	fileName := fmt.Sprintf("r2-bench-%s.parquet", timestamp)
	filePath := filepath.Join(outputDir, fileName)

	file, err := local.NewLocalFileWriter(filePath)
	if err != nil {
		return nil, fmt.Errorf("failed to create parquet file: %w", err)
	}

	pw, err := writer.NewParquetWriter(file, new(main.RequestResult), 4)
	if err != nil {
		file.Close()
		return nil, fmt.Errorf("failed to create parquet writer: %w", err)
	}

	return &ParquetWriter{
		writer:    pw,
		file:      file,
		filePath:  filePath,
		batchSize: batchSize,
		results:   make([]main.RequestResult, 0, batchSize),
	}, nil
}

// WriteResult adds a result to the batch and flushes if batch is full
func (pw *ParquetWriter) WriteResult(result main.RequestResult) error {
	pw.mutex.Lock()
	defer pw.mutex.Unlock()

	pw.results = append(pw.results, result)

	if len(pw.results) >= pw.batchSize {
		return pw.flush()
	}

	return nil
}

// flush writes the current batch to the Parquet file
func (pw *ParquetWriter) flush() error {
	if len(pw.results) == 0 {
		return nil
	}

	for _, result := range pw.results {
		if err := pw.writer.Write(result); err != nil {
			return fmt.Errorf("failed to write result: %w", err)
		}
	}

	pw.results = pw.results[:0]
	return nil
}

// Close flushes any remaining results and closes the writer
func (pw *ParquetWriter) Close() error {
	pw.mutex.Lock()
	defer pw.mutex.Unlock()

	if err := pw.flush(); err != nil {
		return err
	}

	if err := pw.writer.WriteStop(); err != nil {
		return fmt.Errorf("failed to stop parquet writer: %w", err)
	}

	if err := pw.file.Close(); err != nil {
		return fmt.Errorf("failed to close parquet file: %w", err)
	}

	return nil
}

// GetFilePath returns the path of the written file
func (pw *ParquetWriter) GetFilePath() string {
	return pw.filePath
}
