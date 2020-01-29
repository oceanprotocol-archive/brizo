# Brizo Endpoints

## Create new job or restart an existing stopped job

### POST /api/v1/brizo/services/compute


Start a new job

Parameters
```
    signature: String object containg user signature (signed message)
    serviceAgreementId: String object containing agreementID
    jobId: String object containing workflowID (optional)
    algorithmDid: hex str the did of the algorithm to be executed
    algorithmMeta: json object that define the algorithm attributes and url or raw code
    consumerAddress: String object containing owner's address
```

Returns:
A string containing jobId


Example:
```
POST /api/v1/compute?signature=0x00110011&serviceAgreementId=0x1111&algorithmDid=0xa203e320008999099000
```

Output:
```
jobId: "0ba0140c2b8b49418315e2174fde3b71"
```


## Status and Result
  
  
### GET /api/v1/brizo/services/compute
   
   
Get all jobs and corresponding stats

Parameters
```
    signature: String object containg user signature (signed message)
    serviceAgreementId: String object containing agreementID (optional)
    jobId: String object containing workflowID (optional)
    consumerAddress: String object containing owner's address (optional)

    At least one parameter from serviceAgreementId,jobId and owner is required (can be any of them)
```

Returns

An Array of objects, each object describing a workflow. If the array is empty, then the search yields no results

Each object will contain:
```
    owner:The owner of this compute job
    agreementId:
    jobId:
    dateCreated:Unix timestamp of job creation
    dateFinished:Unix timestamp when job finished
    status:  Int, see below for list
    statusText: String, see below
    algologUrl: URL to get the algo log (for user)
    outputsUrl: Array of URLs for algo outputs
    resultsDid: If published, the DID
```

Status description: (see Operator-Service for full status list)



Example:
```
GET /api/v1/brizo/services/compute?signature=0x00110011&serviceAgreementId=0x1111&jobId=012023
```

Output:
```
[
      {
        "owner":"0x1111",
        "agreementId":"0x2222",
        "jobId":"3333",
        "dateCreated":"2020-10-01T01:00:00Z",
        "dateFinished":"2020-10-01T01:00:00Z",
        "status":5,
        "statusText":"Job finished",
        "algologUrl":"http://example.net/logs/algo.log",
        "outputsUrl":[
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
        "algologUrl":"http://example.net/logs2/algo.log",
        "outputsUrl":[
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
    consumerAddress: String object containing owner's address (optional)

    At least one parameter from serviceAgreementId,jobId and owner is required (can be any of them)
```

Returns

Status, whether or not the job was stopped successfully.

Example:
```
PUT /api/v1/brizo/services/compute?signature=0x00110011&serviceAgreementId=0x1111&jobId=012023
```

Output:
```
OK
```

## Delete

### DELETE /api/v1/brizo/services/compute

Delete a compute job and all resources associated with the job. If job is running it will be stopped first.

Parameters
```
    signature: String object containg user signature (signed message)
    serviceAgreementId: String object containing agreementID (optional)
    jobId: String object containing workflowId (optional)
    consumerAddress: String object containing owner's address (optional)

    At least one parameter from serviceAgreementId,jobId and owner is required (can be any of them)
```

Returns

Status, whether or not the job was removed successfully.

Example:
```
DELETE /api/v1/brizo/services/compute?signature=0x00110011&serviceAgreementId=0x1111&jobId=012023
```

Output:
```
OK
```
