# Brizo Endpoints Specification

This document specifies the endpoints for Brizo to be implemented by the core 
developers. The final implementation and its documentation happens in Swagger 
inline code comments and the latest implemented API documentation can be 
accessed via:

- [Docs: Brizo API Reference](https://docs.oceanprotocol.com/references/brizo/)

## Compute endpoints
All compute endpoints respond with an Array of status objects, each object 
describing a compute job info. 

Each status object will contain:
```
    owner:The owner of this compute job
    agreementId:
    jobId:
    dateCreated:Unix timestamp of job creation
    dateFinished:Unix timestamp when job finished
    status:  Int, see below for list
    statusText: String, see below
    algorithmLogUrl: URL to get the algo log (for user)
    resultsUrls: Array of URLs for algo outputs
    resultsDid: If published, the DID
```

Status description (`statusText`): (see Operator-Service for full status list)

| status   | Description               |
|----------|---------------------------|
|  1       | Job started               |
|  2       | Configuring volumes       |
|  3       | Running algorithm         |
|  4       | Filtering results         |
|  5       | Publishing results        |
|  6       | Job completed             |
|  7       | Job stopped               |
|  8       | Job deleted successfully  |


The `output` section required in creating a new compute job looks like this:
```json
{
    "nodeUri": "https://node.oceanprotocol.com",
    "brizoUri": "https://brizo-service..oceanprotocol.com",
    "brizoAddress": "0x01011010101101010993433",
    "metadata": {"name": "Workflow output"},
    "metadataUri": "https://aquarius-service.oceanprotocol.com",
    "secretStoreUri": "https://secret-store.oceanprotocol.com",
    "owner": "0x24f432aab0e22",
    "publishOutput": 1,
    "publishAlgorithmLog": 1
}
```


## Create new job or restart an existing stopped job

### POST /api/v1/brizo/services/compute

Start a new job

Parameters
```
    signature: String object containg user signature (signed message)
    serviceAgreementId: String object containing agreementID
    consumerAddress: String object containing consumer's ethereum address
    output: json object that define the output section, i.e. attributes of the compute results
    algorithmDid: hex str the did of the algorithm to be executed
    algorithmMeta: json object that define the algorithm attributes and url or raw code
    jobId: String object containing workflowID (optional)

    One of `algorithmDid` or `algorithmMeta` is required, `algorithmDid` takes precedence
```

Returns:
Array of `status` objects as described above, in this case the array will have only one object


Example:
```
POST /api/v1/compute?signature=0x00110011&serviceAgreementId=0x1111&algorithmDid=0xa203e320008999099000&consumerAddress=0x990922334
```

Response:

```json
[
    {
      "jobId": "0x1111:001",
      "status": 1,
      "statusText": "Job started",
      ...
    }
]
```


## Status and Result
  
  
### GET /api/v1/brizo/services/compute
   
   
Get all jobs and corresponding stats

Parameters
```
    signature: String object containg user signature (signed message)
    serviceAgreementId: String object containing agreementID (optional)
    jobId: String object containing workflowID (optional)
    consumerAddress: String object containing consumer's address (optional)

    At least one parameter from serviceAgreementId, jobId and owner is required (can be any of them)
```

Returns

Array of `status` objects as described above


Example:
```
GET /api/v1/brizo/services/compute?signature=0x00110011&serviceAgreementId=0x1111&jobId=012023
```

Response:

```json
[
      {
        "owner":"0x1111",
        "agreementId":"0x2222",
        "jobId":"3333",
        "dateCreated":"2020-10-01T01:00:00Z",
        "dateFinished":"2020-10-01T01:00:00Z",
        "status":5,
        "statusText":"Job finished",
        "algorithmLogUrl":"http://example.net/logs/algo.log",
        "resultsUrls":[
            "http://example.net/logs/output/0",
            "http://example.net/logs/output/1"
         ],
         "resultsDid":"did:op:87bdaabb33354d2eb014af5091c604fb4b0f67dc6cca4d18a96547bffdc27bcf"
       },
       {
        "owner":"0x1111",
        "agreementId":"0x2222",
        "jobId":"3334",
        "dateCreated":"2020-10-01T01:00:00Z",
        "dateFinished":"2020-10-01T01:00:00Z",
        "status":5,
        "statusText":"Job finished",
        "algorithmLogUrl":"http://example.net/logs2/algo.log",
        "resultsUrls":[
            "http://example.net/logs2/output/0",
            "http://example.net/logs2/output/1"
         ],
         "resultsDid":""
       }
 ]
 ```
       
## Stop
  
  
### PUT /api/v1/brizo/services/compute

Stop a running compute job.

Parameters
```
    signature: String object containg user signature (signed message)
    serviceAgreementId: String object containing agreementID (optional)
    jobId: String object containing workflowID (optional)
    consumerAddress: String object containing consumer's address (optional)

    At least one parameter from serviceAgreementId,jobId and owner is required (can be any of them)
```

Returns

Array of `status` objects as described above

Example:
```
PUT /api/v1/brizo/services/compute?signature=0x00110011&serviceAgreementId=0x1111&jobId=012023
```

Response:

```json
[
    {
      ...,
      "status": 7,
      "statusText": "Job stopped",
      ...
    }
]
```

## Delete

### DELETE /api/v1/brizo/services/compute

Delete a compute job and all resources associated with the job. If job is running it will be stopped first.

Parameters
```
    signature: String object containg user signature (signed message)
    serviceAgreementId: String object containing agreementID (optional)
    jobId: String object containing workflowId (optional)
    consumerAddress: String object containing consumer's address (optional)

    At least one parameter from serviceAgreementId, jobId is required (can be any of them)
    in addition to consumerAddress and signature
```

Returns

Array of `status` objects as described above

Example:
```
DELETE /api/v1/brizo/services/compute?signature=0x00110011&serviceAgreementId=0x1111&jobId=012023
```

Response:
```json
[
    {
      ...,
      "status": 8,
      "statusText": "Job deleted successfully",
      ...
    }
]
```
