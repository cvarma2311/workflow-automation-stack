# Lightweight Java Data Processing Engine

This project contains a simple, lightweight Java application for performing large-scale data processing tasks. It is designed to be executed from the command line and orchestrated by an external tool like Prefect.

The application has three main functions:
- **generate**: Creates a very large file with mock data.
- **filter**: Streams a file and filters its contents based on a hash function.
- **join**: Joins two datasets based on record IDs.

## How to Build

This is a standard Maven project. To build the executable JAR file, navigate to the `java-engine` directory and run:

```bash
mvn clean package
```

This will produce a file named `java-engine-1.0.0-jar-with-dependencies.jar` in the `target/` directory. This JAR can then be executed by the Prefect workflow.
