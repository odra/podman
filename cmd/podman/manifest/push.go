package manifest

import (
	"fmt"
	"io/ioutil"

	"github.com/containers/common/pkg/auth"
	"github.com/containers/common/pkg/completion"
	"github.com/containers/image/v5/types"
	"github.com/containers/podman/v4/cmd/podman/common"
	"github.com/containers/podman/v4/cmd/podman/registry"
	"github.com/containers/podman/v4/cmd/podman/utils"
	"github.com/containers/podman/v4/pkg/domain/entities"
	"github.com/containers/podman/v4/pkg/util"
	"github.com/spf13/cobra"
)

// manifestPushOptsWrapper wraps entities.ManifestPushOptions and prevents leaking
// CLI-only fields into the API types.
type manifestPushOptsWrapper struct {
	entities.ImagePushOptions

	TLSVerifyCLI   bool // CLI only
	CredentialsCLI string
}

var (
	manifestPushOpts = manifestPushOptsWrapper{}
	pushCmd          = &cobra.Command{
		Use:               "push [options] LIST DESTINATION",
		Short:             "Push a manifest list or image index to a registry",
		Long:              "Pushes manifest lists and image indexes to registries.",
		RunE:              push,
		Example:           `podman manifest push mylist:v1.11 docker://quay.io/myuser/image:v1.11`,
		Args:              cobra.ExactArgs(2),
		ValidArgsFunction: common.AutocompleteImages,
	}
)

func init() {
	registry.Commands = append(registry.Commands, registry.CliCommand{
		Command: pushCmd,
		Parent:  manifestCmd,
	})
	flags := pushCmd.Flags()
	flags.BoolVar(&manifestPushOpts.Rm, "rm", false, "remove the manifest list if push succeeds")
	flags.BoolVar(&manifestPushOpts.All, "all", true, "also push the images in the list")

	authfileFlagName := "authfile"
	flags.StringVar(&manifestPushOpts.Authfile, authfileFlagName, auth.GetDefaultAuthFile(), "path of the authentication file. Use REGISTRY_AUTH_FILE environment variable to override")
	_ = pushCmd.RegisterFlagCompletionFunc(authfileFlagName, completion.AutocompleteDefault)

	certDirFlagName := "cert-dir"
	flags.StringVar(&manifestPushOpts.CertDir, certDirFlagName, "", "use certificates at the specified path to access the registry")
	_ = pushCmd.RegisterFlagCompletionFunc(certDirFlagName, completion.AutocompleteDefault)

	credsFlagName := "creds"
	flags.StringVar(&manifestPushOpts.CredentialsCLI, credsFlagName, "", "use `[username[:password]]` for accessing the registry")
	_ = pushCmd.RegisterFlagCompletionFunc(credsFlagName, completion.AutocompleteNone)

	digestfileFlagName := "digestfile"
	flags.StringVar(&manifestPushOpts.DigestFile, digestfileFlagName, "", "after copying the image, write the digest of the resulting digest to the file")
	_ = pushCmd.RegisterFlagCompletionFunc(digestfileFlagName, completion.AutocompleteDefault)

	formatFlagName := "format"
	flags.StringVarP(&manifestPushOpts.Format, formatFlagName, "f", "", "manifest type (oci or v2s2) to attempt to use when pushing the manifest list (default is manifest type of source)")
	_ = pushCmd.RegisterFlagCompletionFunc(formatFlagName, common.AutocompleteManifestFormat)

	flags.BoolVarP(&manifestPushOpts.RemoveSignatures, "remove-signatures", "", false, "don't copy signatures when pushing images")

	signByFlagName := "sign-by"
	flags.StringVar(&manifestPushOpts.SignBy, signByFlagName, "", "sign the image using a GPG key with the specified `FINGERPRINT`")
	_ = pushCmd.RegisterFlagCompletionFunc(signByFlagName, completion.AutocompleteNone)

	flags.BoolVar(&manifestPushOpts.TLSVerifyCLI, "tls-verify", true, "require HTTPS and verify certificates when accessing the registry")
	flags.BoolVarP(&manifestPushOpts.Quiet, "quiet", "q", false, "don't output progress information when pushing lists")
	flags.SetNormalizeFunc(utils.AliasFlags)

	compressionFormat := "compression-format"
	flags.StringVar(&manifestPushOpts.CompressionFormat, compressionFormat, "", "compression format to use")
	_ = pushCmd.RegisterFlagCompletionFunc(compressionFormat, common.AutocompleteCompressionFormat)

	if registry.IsRemote() {
		_ = flags.MarkHidden("cert-dir")
	}
}

func push(cmd *cobra.Command, args []string) error {
	if err := auth.CheckAuthFile(manifestPushOpts.Authfile); err != nil {
		return err
	}
	listImageSpec := args[0]
	destSpec := args[1]
	if listImageSpec == "" {
		return fmt.Errorf(`invalid image name "%s"`, listImageSpec)
	}
	if destSpec == "" {
		return fmt.Errorf(`invalid destination "%s"`, destSpec)
	}

	if manifestPushOpts.CredentialsCLI != "" {
		creds, err := util.ParseRegistryCreds(manifestPushOpts.CredentialsCLI)
		if err != nil {
			return err
		}
		manifestPushOpts.Username = creds.Username
		manifestPushOpts.Password = creds.Password
	}

	// TLS verification in c/image is controlled via a `types.OptionalBool`
	// which allows for distinguishing among set-true, set-false, unspecified
	// which is important to implement a sane way of dealing with defaults of
	// boolean CLI flags.
	if cmd.Flags().Changed("tls-verify") {
		manifestPushOpts.SkipTLSVerify = types.NewOptionalBool(!manifestPushOpts.TLSVerifyCLI)
	}
	digest, err := registry.ImageEngine().ManifestPush(registry.Context(), args[0], args[1], manifestPushOpts.ImagePushOptions)
	if err != nil {
		return err
	}
	if manifestPushOpts.DigestFile != "" {
		if err := ioutil.WriteFile(manifestPushOpts.DigestFile, []byte(digest), 0644); err != nil {
			return err
		}
	}

	return nil
}
