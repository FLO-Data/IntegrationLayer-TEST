-- Create table for kovaci linka scans
CREATE TABLE kovaci_linka_scans (
    id INT IDENTITY(1,1) PRIMARY KEY,
    gitter_id VARCHAR(50) NOT NULL,
    employee_id VARCHAR(100) NOT NULL,
    timestamp DATETIME DEFAULT GETDATE(),
    position CHAR(1) NOT NULL CHECK (position IN ('A', 'B'))
);

-- Create stored procedure for inserting kovaci linka scans
CREATE PROCEDURE InsertKovaciLinkaScan
    @gitter_id VARCHAR(50),
    @employee_id VARCHAR(100),
    @position CHAR(1)
AS
BEGIN
    SET NOCOUNT ON;
    
    BEGIN TRY
        INSERT INTO kovaci_linka_scans (gitter_id, employee_id, position)
        VALUES (@gitter_id, @employee_id, @position);
        
        SELECT SCOPE_IDENTITY() AS id;
    END TRY
    BEGIN CATCH
        DECLARE @ErrorMessage NVARCHAR(4000) = ERROR_MESSAGE();
        DECLARE @ErrorSeverity INT = ERROR_SEVERITY();
        DECLARE @ErrorState INT = ERROR_STATE();
        
        RAISERROR (@ErrorMessage, @ErrorSeverity, @ErrorState);
    END CATCH
END; 