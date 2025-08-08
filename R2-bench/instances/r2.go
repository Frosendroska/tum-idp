package instances

import (
	"context"
	"fmt"
	"io"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/credentials"
	"github.com/aws/aws-sdk-go-v2/service/s3"
	"github.com/aws/aws-sdk-go-v2/service/s3/types"
	"errors"
	"bytes"
)

// R2Client handles Cloudflare R2 storage operations
type R2Client struct {
	client     *s3.Client
	bucketName string
	endpoint   string
}

// NewR2Client creates a new R2 client
func NewR2Client(accountID, accessKeyID, secretAccessKey, bucketName string) (*R2Client, error) {
	// R2 endpoint format: https://<ACCOUNT_ID>.r2.cloudflarestorage.com
	endpoint := fmt.Sprintf("https://%s.r2.cloudflarestorage.com", accountID)

	// Create custom configuration for R2
	customResolver := aws.EndpointResolverWithOptionsFunc(func(service, region string, options ...interface{}) (aws.Endpoint, error) {
		return aws.Endpoint{
			URL: endpoint,
		}, nil
	})

	cfg, err := config.LoadDefaultConfig(context.TODO(),
		config.WithEndpointResolverWithOptions(customResolver),
		config.WithCredentialsProvider(credentials.NewStaticCredentialsProvider(accessKeyID, secretAccessKey, "")),
		config.WithRegion("auto"), // R2 uses "auto" region
	)
	if err != nil {
		return nil, fmt.Errorf("failed to load config: %w", err)
	}

	client := s3.NewFromConfig(cfg)

	return &R2Client{
		client:     client,
		bucketName: bucketName,
		endpoint:   endpoint,
	}, nil
}

// GetObjectRange retrieves a range of bytes from an object
func (r2 *R2Client) GetObjectRange(ctx context.Context, objectKey string, start, length int64) ([]byte, error) {
	rangeHeader := fmt.Sprintf("bytes=%d-%d", start, start+length-1)

	input := &s3.GetObjectInput{
		Bucket: aws.String(r2.bucketName),
		Key:    aws.String(objectKey),
		Range:  aws.String(rangeHeader),
	}

	result, err := r2.client.GetObject(ctx, input)
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

// UploadObject uploads an object to R2
func (r2 *R2Client) UploadObject(ctx context.Context, objectKey string, data []byte) error {
	input := &s3.PutObjectInput{
		Bucket: aws.String(r2.bucketName),
		Key:    aws.String(objectKey),
		Body:   bytes.NewReader(data),
	}

	_, err := r2.client.PutObject(ctx, input)
	if err != nil {
		return fmt.Errorf("failed to upload object: %w", err)
	}

	return nil
}

// ObjectExists checks if an object exists
func (r2 *R2Client) ObjectExists(ctx context.Context, objectKey string) (bool, error) {
	input := &s3.HeadObjectInput{
		Bucket: aws.String(r2.bucketName),
		Key:    aws.String(objectKey),
	}

	_, err := r2.client.HeadObject(ctx, input)
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
func (r2 *R2Client) GetObjectSize(ctx context.Context, objectKey string) (int64, error) {
	input := &s3.HeadObjectInput{
		Bucket: aws.String(r2.bucketName),
		Key:    aws.String(objectKey),
	}

	result, err := r2.client.HeadObject(ctx, input)
	if err != nil {
		return 0, fmt.Errorf("failed to get object size: %w", err)
	}

	return result.ContentLength, nil
}

// GetEndpoint returns the R2 endpoint
func (r2 *R2Client) GetEndpoint() string {
	return r2.endpoint
}
