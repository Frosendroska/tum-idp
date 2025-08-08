package instances

import (
	"context"
	"fmt"
	"io"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/service/s3"
	"github.com/aws/aws-sdk-go-v2/service/s3/types"
	"errors"
	"bytes"
)

// S3Client handles AWS S3 storage operations
type S3Client struct {
	client     *s3.Client
	bucketName string
	region     string
}

// NewS3Client creates a new S3 client
func NewS3Client(region, bucketName string) (*S3Client, error) {
	cfg, err := config.LoadDefaultConfig(context.TODO(),
		config.WithRegion(region),
	)
	if err != nil {
		return nil, fmt.Errorf("failed to load config: %w", err)
	}

	client := s3.NewFromConfig(cfg)

	return &S3Client{
		client:     client,
		bucketName: bucketName,
		region:     region,
	}, nil
}

// GetObjectRange retrieves a range of bytes from an object
func (s3c *S3Client) GetObjectRange(ctx context.Context, objectKey string, start, length int64) ([]byte, error) {
	rangeHeader := fmt.Sprintf("bytes=%d-%d", start, start+length-1)

	input := &s3.GetObjectInput{
		Bucket: aws.String(s3c.bucketName),
		Key:    aws.String(objectKey),
		Range:  aws.String(rangeHeader),
	}

	result, err := s3c.client.GetObject(ctx, input)
	if err != nil {
		return nil, fmt.Errorf("failed to get object range: %w", err)
	}
	defer result.Body.Close()

	body, err := io.ReadAll(result.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read object body: %w", err)
	}

	return body, nil
}

// UploadObject uploads an object to S3
func (s3c *S3Client) UploadObject(ctx context.Context, objectKey string, data []byte) error {
	input := &s3.PutObjectInput{
		Bucket: aws.String(s3c.bucketName),
		Key:    aws.String(objectKey),
		Body:   bytes.NewReader(data),
	}

	_, err := s3c.client.PutObject(ctx, input)
	if err != nil {
		return fmt.Errorf("failed to upload object: %w", err)
	}

	return nil
}

// ObjectExists checks if an object exists
func (s3c *S3Client) ObjectExists(ctx context.Context, objectKey string) (bool, error) {
	input := &s3.HeadObjectInput{
		Bucket: aws.String(s3c.bucketName),
		Key:    aws.String(objectKey),
	}

	_, err := s3c.client.HeadObject(ctx, input)
	if err != nil {
		// Check if it's a "not found" error
		var notFoundErr *types.NoSuchKey
		if errors.As(err, &notFoundErr) {
			return false, nil
		}
		return false, fmt.Errorf("failed to check object existence: %w", err)
	}

	return true, nil
}

// GetObjectSize returns the size of an object
func (s3c *S3Client) GetObjectSize(ctx context.Context, objectKey string) (int64, error) {
	input := &s3.HeadObjectInput{
		Bucket: aws.String(s3c.bucketName),
		Key:    aws.String(objectKey),
	}

	result, err := s3c.client.HeadObject(ctx, input)
	if err != nil {
		return 0, fmt.Errorf("failed to get object size: %w", err)
	}

	return result.ContentLength, nil
}

// GetEndpoint returns the S3 endpoint
func (s3c *S3Client) GetEndpoint() string {
	return fmt.Sprintf("https://s3.%s.amazonaws.com", s3c.region)
}
