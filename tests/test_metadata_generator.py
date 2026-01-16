"""Tests for Fabric metadata generator."""

from fabric_hydrate.metadata_generator import FabricMetadataGenerator
from fabric_hydrate.models import ColumnSchema, TableMetadata


class TestFabricMetadataGenerator:
    """Tests for FabricMetadataGenerator class."""

    def test_generate_basic_metadata(self, sample_table_metadata: TableMetadata) -> None:
        """Test generating basic Fabric metadata."""
        generator = FabricMetadataGenerator()
        result = generator.generate(sample_table_metadata)

        assert result.name == "test_table"
        assert result.description == "Test table"
        assert len(result.columns) == 5
        assert result.partitionBy == ["created_at"]

    def test_type_conversion(self) -> None:
        """Test Delta to Fabric type conversion."""
        generator = FabricMetadataGenerator()

        test_cases = [
            ("string", "String"),
            ("long", "Int64"),
            ("integer", "Int32"),
            ("short", "Int16"),
            ("byte", "Int8"),
            ("float", "Single"),
            ("double", "Double"),
            ("boolean", "Boolean"),
            ("binary", "Binary"),
            ("date", "Date"),
            ("timestamp", "DateTime"),
            ("timestamp_ntz", "DateTime"),
        ]

        for delta_type, expected_fabric_type in test_cases:
            result = generator._convert_type(delta_type)
            assert result == expected_fabric_type, f"Failed for {delta_type}"

    def test_decimal_type_conversion(self) -> None:
        """Test decimal type conversion preserves precision."""
        generator = FabricMetadataGenerator()

        result = generator._convert_type("decimal(18,4)")
        assert result == "Decimal(18,4)"

    def test_array_type_conversion(self) -> None:
        """Test array type conversion."""
        generator = FabricMetadataGenerator()

        result = generator._convert_type("array<string>")
        assert result == "Array<String>"

        result = generator._convert_type("array<long>")
        assert result == "Array<Int64>"

    def test_complex_type_conversion(self) -> None:
        """Test complex types convert to Object."""
        generator = FabricMetadataGenerator()

        # Map type
        result = generator._convert_type("map<string,integer>")
        assert result == "Object"

        # Struct type
        result = generator._convert_type("struct<name:string,age:integer>")
        assert result == "Object"

    def test_semantic_type_inference(self) -> None:
        """Test semantic type inference from column names."""
        generator = FabricMetadataGenerator()

        # Email
        assert generator._infer_semantic_type("email", "string") == "Email"
        assert generator._infer_semantic_type("user_email", "string") == "Email"

        # URL
        assert generator._infer_semantic_type("website_url", "string") == "URL"
        assert generator._infer_semantic_type("profile_link", "string") == "URL"

        # Geographic
        assert generator._infer_semantic_type("latitude", "double") == "Latitude"
        assert generator._infer_semantic_type("lng", "double") == "Longitude"
        assert generator._infer_semantic_type("country", "string") == "Country"
        assert generator._infer_semantic_type("city", "string") == "City"
        assert generator._infer_semantic_type("zip_code", "string") == "PostalCode"

        # Currency
        assert generator._infer_semantic_type("price", "decimal(10,2)") == "Currency"
        assert generator._infer_semantic_type("total_amount", "double") == "Currency"

        # Identifier
        assert generator._infer_semantic_type("customer_id", "long") == "Identifier"
        assert generator._infer_semantic_type("id", "long") == "Identifier"

        # No semantic type
        assert generator._infer_semantic_type("some_column", "string") is None

    def test_display_name_generation(self) -> None:
        """Test display name generation."""
        generator = FabricMetadataGenerator()

        # Snake case
        assert generator._generate_display_name("first_name") == "First Name"
        assert generator._generate_display_name("created_at") == "Created At"

        # Camel case
        assert generator._generate_display_name("firstName") == "First Name"
        assert generator._generate_display_name("createdAt") == "Created At"

        # Mixed
        assert generator._generate_display_name("user_firstName") == "User First Name"

    def test_properties_include_source_info(self, sample_table_metadata: TableMetadata) -> None:
        """Test that properties include source information."""
        generator = FabricMetadataGenerator()
        result = generator.generate(sample_table_metadata)

        assert result.properties["source"] == "delta-lake"
        assert result.properties["generatedBy"] == "fabric-hydrate"

    def test_delta_properties_preserved(self) -> None:
        """Test that Delta properties are preserved."""
        metadata = TableMetadata(
            name="test",
            location="/path",
            columns=[],
            properties={
                "delta.minReaderVersion": "2",
                "delta.minWriterVersion": "5",
                "custom.property": "value",
            },
        )

        generator = FabricMetadataGenerator()
        result = generator.generate(metadata)

        assert "delta.minReaderVersion" in result.properties
        assert "delta.minWriterVersion" in result.properties
        # Non-delta properties not included
        assert "custom.property" not in result.properties

    def test_full_column_conversion(self) -> None:
        """Test full column conversion with all fields."""
        metadata = TableMetadata(
            name="test",
            location="/path",
            columns=[
                ColumnSchema(
                    name="user_email",
                    type="string",
                    nullable=True,
                    description="User email address",
                ),
            ],
        )

        generator = FabricMetadataGenerator()
        result = generator.generate(metadata)

        col = result.columns[0]
        assert col.name == "user_email"
        assert col.dataType == "String"
        assert col.isNullable is True
        assert col.description == "User email address"
        assert col.displayName == "User Email"
        assert col.semanticType == "Email"

    def test_datetime_semantic_type(self) -> None:
        """Test datetime semantic type inference."""
        generator = FabricMetadataGenerator()

        assert generator._infer_semantic_type("created_at", "timestamp") == "DateTime"
        assert generator._infer_semantic_type("updated_at", "timestamp") == "DateTime"
        assert generator._infer_semantic_type("modified_at", "timestamp") == "DateTime"
        assert generator._infer_semantic_type("birth_date", "date") == "Date"

    def test_unknown_type_capitalized(self) -> None:
        """Test unknown types are capitalized."""
        generator = FabricMetadataGenerator()

        result = generator._convert_type("unknown_type")
        assert result == "Unknown_type"

    def test_uri_semantic_type(self) -> None:
        """Test URI semantic type inference."""
        generator = FabricMetadataGenerator()

        assert generator._infer_semantic_type("href", "string") == "URL"
        assert generator._infer_semantic_type("uri", "string") == "URL"

    def test_postal_code_semantic_type(self) -> None:
        """Test postal code semantic type inference."""
        generator = FabricMetadataGenerator()

        assert generator._infer_semantic_type("postal_code", "string") == "PostalCode"

    def test_revenue_currency_type(self) -> None:
        """Test revenue/cost semantic type."""
        generator = FabricMetadataGenerator()

        assert generator._infer_semantic_type("revenue", "double") == "Currency"
        assert generator._infer_semantic_type("cost", "decimal(10,2)") == "Currency"

    def test_generate_with_description(self) -> None:
        """Test generation preserves table description."""
        metadata = TableMetadata(
            name="test",
            location="/path",
            columns=[],
            description="My test table description",
        )

        generator = FabricMetadataGenerator()
        result = generator.generate(metadata)

        assert result.description == "My test table description"

    def test_generate_empty_columns(self) -> None:
        """Test generation with empty columns."""
        metadata = TableMetadata(
            name="test",
            location="/path",
            columns=[],
        )

        generator = FabricMetadataGenerator()
        result = generator.generate(metadata)

        assert result.name == "test"
        assert len(result.columns) == 0
